#!/usr/bin/env python

"""Usage: git-remote-cvs <remote> [<url>]

Git remote helper command for interacting with CVS repositories

See git-remote-helpers documentation for details on external interface,
usage, etc.  See git-remote-cvs documentation for specific
configuration details of this remote helper.

"""

# PRINCIPLES:
# -----------
# - Importing same symbol twice (with no CVS changes in between) should
#   yield the exact same Git state (and the second import should have
#   no commits).
# - Importing several CVS symbols pointing to the same state should
#   yield corresponding refs pointing to the _same_ commit in Git.
# - Importing a CVS symbol which has received only "regular commits"
#   since last import should yield a fast-forward straight line of
#   commits.

# TODO / KNOWN PROBLEMS:
# ----------------------
# - Remove cachedSymbolsOnly config variable for now?
# - Author map handling; map CVS usernames to Git full name + email
# - Handle files that have been created AND deleted since last import
# - How to handle CVS tags vs. branches.  Turn CVS tags into Git tags?
# - Better CVS branch handling: When a branch as a super/subset of
#   files/revs compared to another branch, find a way to base one branch
#   on the other instead of creating parallel lines of development with
#   roughly the same commits.
# - Profiling, optimizations...

import sys
import os

from git_remote_cvs.util import (debug, error, die, ProgressIndicator,
                                 run_command)
from git_remote_cvs.cvs import CVSState, CVSWorkDir, fetch_revs
from git_remote_cvs.git import (get_git_dir, parse_git_config, git_config_bool,
                                valid_git_ref, GitObjectFetcher, GitRefMap,
                                GitFICommit, GitFastImport, GitNotes)
from git_remote_cvs.cvs_symbol_cache import CVSSymbolCache
from git_remote_cvs.commit_states import CommitStates
from git_remote_cvs.cvs_revision_map import CVSRevisionMap, CVSStateMap
from git_remote_cvs.changeset import build_changesets_from_revs


class Config(object):

    """Encapsulation of configuration variables."""

    # Author name/email tuple for commits created by this tool
    Author = ("git remote-cvs", "invalid@example.com")
    # Git remote name
    Remote = None
    # CVS symbols are imported into this refs namespace/directory
    RefSpace = None
    # Git notes ref, the refname pointing to our git notes
    NotesRef = None
    # CVS repository identifier, a 2-tuple (cvs_root, cvs_module),
    # where cvs_root is the CVS server/repository URL (as found in
    # $CVSROOT, or in a CVS/Root file), and cvs_module is the path
    # to a CVS module relative to the CVS repository (as found in a
    # CVS/Repository file)
    CVSRepo = (None, None)
    # Path to the git-remote-cvs cache/work directory
    # (normally "info/cvs/$remote" within $GIT_DIR)
    WorkDir = None
    # If False, the list of CVS symbols will always be retrieved from
    # the CVS server using 'cvs rlog'.  If True, only the cached
    # symbols within the "symbols" subdirectory of WorkDir are
    # consulted.
    CachedSymbolsOnly = False

    @classmethod
    def init (cls, remote):
        """Fetch and setup configuration for the given remote."""
        git_config = parse_git_config()
        assert git_config["remote.%s.vcs" % (remote)] == "cvs"

        cls.Author = (git_config["user.name"], git_config["user.email"])
        cls.Remote = remote
        cls.RefSpace = "refs/cvs/%s/" % (remote)
        cls.NotesRef = "refs/notes/cvs/%s" % (remote)
        cls.CVSRepo = (git_config["remote.%s.cvsroot" % (remote)],
                       git_config["remote.%s.cvsmodule" % (remote)])
        cls.WorkDir = os.path.join(get_git_dir(), "info/cvs", remote)
        cls.CachedSymbolsOnly = git_config_bool(git_config.get(
            "remote.%s.cachedsymbolsonly" % (remote), "false"))


def work_path (*args):
    """Return the given path appended to git-remote-cvs's cache/work dir."""
    return os.path.join(Config.WorkDir, *args)


def cvs_to_refname (cvsname):
    """Return the git ref name for the given CVS symbolic name."""
    if cvsname.startswith(Config.RefSpace):  # Already converted
        return cvsname
    return Config.RefSpace + cvsname


def ref_to_cvsname (refname):
    """Return the CVS symbolic name for the given git ref name."""
    if refname.startswith(Config.RefSpace):
        return refname[len(Config.RefSpace):]
    return refname


def valid_cvs_symbol (symbol):
    """Return True iff the given CVS symbol can be imported into Git."""
    return valid_git_ref(cvs_to_refname(symbol))


def die_usage (msg, *args):
    """Abort program with a helpful usage message."""
    # Use this file's docstring as a usage string
    print >> sys.stderr, __doc__
    die(msg, *args)


def import_cvs_revs (symbol, prev_state, cur_state, progress):
    """Import the CVS revisions needed to satisfy the given CVS symbol.

    This method will determine the CVS revisions involved in moving
    from the given prev_state to the given cur_state.  This includes
    looking at revision metadata in CVS, and importing needed blobs
    from CVS.

    The revision metadata is returned as a 2-level dict of CVSRev
    objects: mapping path -> revnum -> CVSRev object.

    """
    # Calculate the revisions involved in moving from prev_state to
    # cur_state, and fetch CVSRev objects for these revisions.
    progress.pushprefix("Importing CVS revisions: ")
    paths = set(prev_state.paths()).union(cur_state.paths())
    num_fetched_revs = 0  # Number of CVSRev objects involved
    num_imported_blobs = 0  # Number of blobs actually imported
    cvs_revs = {}  # path -> revnum -> CVSRev
    for i, path in enumerate(sorted(paths)):
        progress.pushprefix("(%i/%i) %s: " % (i + 1, len(paths), path))
        progress("")
        prev_rev = prev_state.get(path)
        cur_rev = cur_state.get(path)
        if prev_rev and cur_rev and prev_rev == cur_rev:
            # No changes since last import
            progress.popprefix()
            continue

        # Fetch CVSRev objects for range [path:prev_rev, path:symbol]
        path_revs = fetch_revs(path, prev_rev, cur_rev, symbol, Config.CVSRepo)
        if not path_revs:
            # Failed to find revs between prev_rev and symbol
            if cur_rev:
                assert not cur_rev.follows(prev_rev)
                # The CVS symbol has been moved/reset since the
                # last import in such a way that we cannot
                # deduce the history between the last import
                # and the current import.
                # FIXME: Can we can work around this?
                die("CVS symbol %s has been moved/reset from %s:%s to %s:%s "
                    "since the last import.  This is not supported",
                    symbol, path, prev_rev, path, cur_rev)
            else:
                # CVS symbol has been removed from this path.
                # We cannot conclusively determine the history
                # of this path following prev_rev.
                # FIXME: Can we can work around this?
                die("CVS symbol %s has been removed from %s since the last "
                    "import.  This is not supported",
                    symbol, path)

        # OK.  We've got the revs in range [prev_rev, symbol]
        # Verify/determine cur_rev
        real_cur_rev = max(path_revs.keys())
        if cur_rev:
            assert cur_rev == real_cur_rev
        else: cur_rev = real_cur_rev
        # No need to re-import prev_rev if already imported
        if prev_rev:
            assert cur_rev.follows(prev_rev)
            assert prev_rev in path_revs
            del path_revs[prev_rev]
        assert path_revs  # There should be more revs than just prev_rev

        # Sanity checks:
        # All revs from prev_rev to cur_rev are about to be imported
        check_rev = cur_rev
        while check_rev and check_rev != prev_rev:
            assert check_rev in path_revs
            check_rev = check_rev.parent()
        # All previous revs have already been imported
        check_rev = prev_rev
        while check_rev:
            assert Globals.CVSRevisionMap.has_rev(path, check_rev)
            check_rev = check_rev.parent()

        # Import CVS revisions as Git blobs
        j = 0
        for num, rev in sorted(path_revs.iteritems(), reverse = True):
            j += 1
            progress("(%i/%i) %s" % (j, len(path_revs), num))
            assert num == rev.num
            # Skip if already imported
            if Globals.CVSRevisionMap.has_rev(rev.path, rev.num):
                continue
            # ...or if rev is a deletion
            elif rev.deleted:
                continue
            # Import blob for reals
            data = Globals.CVSWorkDir.get_revision_data(rev.path, rev.num)
            Globals.GitFastImport.comment("Importing CVS revision %s:%s" %
                                          (rev.path, rev.num))
            mark = Globals.GitFastImport.blob(data)
            Globals.CVSRevisionMap.add_blob(rev.path, rev.num, mark)
            num_imported_blobs += 1

        # Add path_revs to the overall structure of revs to be imported
        assert path not in cvs_revs
        cvs_revs[path] = path_revs
        num_fetched_revs += len(path_revs)
        progress.popprefix()
    progress.popprefix()
    progress("Imported %i blobs (reused %i existing blobs)" %
             (num_imported_blobs, num_fetched_revs - num_imported_blobs), True)

    return cvs_revs


def advance_state (state, changeset):
    """Advance the given state by applying the given changeset."""
    # Verify that the given changeset "fits" on top of the given state
    for rev in changeset:
        prev_num = rev.num.parent()
        state_num = state.get(rev.path)
        if prev_num is None and state_num is None:
            # rev is the first revision of this path being added
            state.add(rev.path, rev.num)
        elif prev_num and state_num and prev_num == state_num:
            if rev.deleted:  # rev deletes path from state
                state.remove(rev.path, prev_num)
            else:  # rev follows state's revision of this path
                state.replace(rev.path, rev.num)
        else:
            error("Cannot apply changeset with %s:%s on top of CVS state "
                  "with %s:%s.",
                  rev.path, changeset[rev.path].num,
                  rev.path, state.get(rev.path))
            error("    changeset: %s", changeset)
            error("    CVS state: \n---\n%s---", state)
            die("Failed to apply changeset.  Aborting.")


def revert_state (state, changeset):
    """Revert the given state to before the given changeset is applied.

    This is the reverse of the above advance_state() function.

    """
    for rev in changeset:
        prev_num = rev.num.parent()
        state_num = state.get(rev.path)
        if state_num is None:  # Revert deletion of file
            assert rev.deleted
            state.add(rev.path, prev_num)
        else:
            assert state_num == rev.num
            if prev_num is None:  # Revert addition of file
                state.remove(rev.path, rev.num)
            else:  # Regular revert to previous version
                state.replace(rev.path, prev_num)


def import_changesets (ref, changesets, from_state, to_state, progress):
    """Apply the given list of Changeset objects to the given ref.

    Also verify that the changesets bring us from the given from_state
    to the given to_state.

    """
    state = from_state
    for i, c in enumerate(changesets):
        advance_state(state, c)
        progress("(%i/%i) Committing %s" % (i + 1, len(changesets), c))
        # Make a git commit from changeset c
        commitdata = GitFICommit(
            c.author, c.author + "@example.com",  # TODO: author_map handling
            c.date.ts, c.date.tz_str(),
            "".join(["%s\n" % (line) for line in c.message]))

        for rev in c:
            p, n = rev.path, rev.num
            if rev.deleted:
                commitdata.delete(p)
                continue
            blobname = Globals.CVSRevisionMap.get_blob(p, n)
            mode = Globals.CVSRevisionMap.get_mode(p)
            if mode is None:  # Must retrieve mode from CVS checkout
                debug("Retrieving mode info for '%s'" % (p))
                Globals.CVSWorkDir.update(n, [p])
                mode = Globals.CVSWorkDir.get_modeinfo([p])[p]
                Globals.CVSRevisionMap.add_path(p, mode)
            commitdata.modify(mode, blobname, p)

        commitname = Globals.GitFastImport.commit(ref, commitdata)
        Globals.CommitStates.add(commitname, state, Globals.GitFastImport)
        for path, revnum in state:
            Globals.CVSRevisionMap.add_commit(path, revnum, commitname)
        assert commitname in Globals.CVSStateMap.get_commits(state)
    assert state == to_state
    return len(changesets)


def import_cvs_symbol (cvs_symbol, progress):
    """Import the given CVS symbol from CVS to Git.

    Return False if nothing was imported, True otherwise.

    """
    git_ref = cvs_to_refname(cvs_symbol)
    progress.pushprefix("%s: " % (cvs_symbol))

    # Verify that we are asked to import valid git ref names
    if not valid_git_ref(git_ref):
        progress("Invalid git ref '%s'.  Skipping." % (git_ref), True)
        progress.popprefix()
        return False

    # Retrieve previously imported CVS state
    progress("Loading previously imported state of %s..." % (git_ref))
    prev_commit = Globals.GitRefMap.get(git_ref)
    prev_state = Globals.CommitStates.get(prev_commit, CVSState())

    # Retrieve current CVS state of symbol
    # Also: At some point we will need mode information for all CVS
    # paths (stored in CVSRevisionMap).  This information can be added
    # for each path on demand (using CVSWorkDir.get_modeinfo()), but
    # doing so may be an expensive process.  It is much cheaper to load
    # mode information for as many paths as possible in a _single_
    # operation.  We do this below, by calling
    # CVSRevisionMap.sync_modeinfo_from_cvs() in appropriate places.
    if Config.CachedSymbolsOnly:
        progress("Synchronizing local CVS symbol cache for symbol...")
        # The symbol cache is likely not up-to-date.  Synchronize the
        # given CVS symbol explicitly, to make sure we get the version
        # current with the CVS server.
        Globals.CVSSymbolCache.sync_symbol(cvs_symbol, Globals.CVSWorkDir,
                                           progress)
        # The above method updates the CVS workdir to the current CVS
        # version.  Hence, now is a convenient time to preload mode
        # info from the currently checked-out CVS files.  There may be
        # more files for which we'll need mode information, but we'll
        # deal with those when needed.
        progress("Updating path mode info from current CVS checkout.")
        Globals.CVSRevisionMap.sync_modeinfo_from_cvs(Globals.CVSWorkDir)
    elif not Globals.CVSRevisionMap:  # No info for any paths, yet
        # Pure optimization: We didn't get to preload all the mode info
        # above.  Normally, the only alternative is load mode info for
        # each path on-demand.  However, if our CVSRevisionMap is
        # currently empty, that's probably going to be very expensive.
        # Therefore, in this case, do an explicit CVS update here, and
        # preload mode info for all paths.
        progress("Updating CVS checkout to sync path mode info.")
        Globals.CVSWorkDir.update(cvs_symbol)
        Globals.CVSRevisionMap.sync_modeinfo_from_cvs(Globals.CVSWorkDir)

    progress("Loading current CVS state...")
    try:
        cur_state = Globals.CVSSymbolCache[cvs_symbol]
    except KeyError:
        progress("Couldn't find symbol '%s'.  Skipping." % (cvs_symbol), True)
        progress.popprefix()
        return False

    # Optimization: Check if the previous import of this symbol is
    # still up-to-date.  If so, there's nothing more to be done.
    progress("Checking if we're already up-to-date...")
    if cur_state == prev_state:
        progress("Already up-to-date.  Skipping.", True)
        progress.popprefix()
        return False

    progress("Fetching CVS revisions...")
    cvs_revs = import_cvs_revs(cvs_symbol, prev_state, cur_state, progress)
    progress("Organizing revisions into chronological list of changesets...")
    changesets = build_changesets_from_revs(cvs_revs)

    # When importing a new branch, try to optimize branch start point,
    # instead of importing entire branch from scratch
    if prev_commit is None:
        progress("Finding startpoint for new symbol...")
        i = len(changesets)
        state = cur_state.copy()
        for c in reversed(changesets):
            commit = Globals.CVSStateMap.get_exact_commit(state,
                                                          Globals.CommitStates)
            if commit is not None:
                # We have found a commit that exactly matches the state
                # after commit #i (changesets[i - 1])
                Globals.GitFastImport.reset(git_ref, commit)
                changesets = changesets[i:]
                break
            revert_state(state, c)
            i -= 1
    num_changesets = len(changesets)
    num_applied = 0

    # Apply changesets, bringing git_ref from prev_state to cur_state
    if num_changesets:
        progress("Importing changesets...")
        num_applied = import_changesets(git_ref, changesets, prev_state,
                                        cur_state, progress)
    progress("Imported %i changesets (reused %i existing changesets)" %
             (num_applied, num_changesets - num_applied), True)
    progress.popprefix()
    return True


def do_import (*args):
    """Do the 'import' command; import refs from a remote."""
    if not args:
        die_usage("'import' takes at least one parameter: ref...")

    progress = ProgressIndicator("    ", sys.stderr)
    cvs_symbols = map(ref_to_cvsname, args)
    empty_import = True
    for symbol in cvs_symbols:
        if import_cvs_symbol(symbol, progress):
            empty_import = False
    if empty_import:
        progress.finish("Everything up-to-date", True)
        return 0
    progress.finish("Finished importing %i CVS symbols to Git" %
                    (len(cvs_symbols)), True)
    return 0


def do_list (*args):
    """Do the 'list' command; list refs available from a CVS remote."""
    if args:
        die_usage("'list' takes no parameters")

    progress = ProgressIndicator("    ", sys.stderr)
    if Config.CachedSymbolsOnly:
        progress("Listing symbols in local symbol cache...", True)
        for symbol in sorted(Globals.CVSSymbolCache):
            print cvs_to_refname(symbol)
        progress.finish()
        print  # Terminate output with a blank line
        return 0

    # Synchronize local symbol cache with CVS server
    progress("Synchronizing local symbol cache with CVS server...")
    Globals.CVSSymbolCache.sync_all_symbols(Config.CVSRepo, progress,
                                            valid_cvs_symbol)
    # Load current states of Git refs
    progress("Loading current state of Git refs...")
    changed, unchanged = 0, 0
    for cvs_symbol, cvs_state in sorted(Globals.CVSSymbolCache.items()):
        git_ref = cvs_to_refname(cvs_symbol)
        progress("\tChecking if Git ref is up-to-date: %s" % (git_ref))
        git_commit = Globals.GitRefMap.get(git_ref)
        git_state = Globals.CommitStates.get(git_commit)
        attrs = ""
        if git_state and git_state == cvs_state:
            attrs = " unchanged"
            unchanged += 1
        else:
            git_commit = "?"
            changed += 1
        print "%s %s%s" % (git_commit, git_ref, attrs)
    progress.finish("Found %i CVS symbols (%i changed, %i unchanged)" %
                    (changed + unchanged, changed, unchanged))
    print  # Terminate with a blank line
    return 0


def do_capabilities (*args):
    """Do the 'capabilities' command; report supported features."""
    if args:
        die_usage("'capabilities' takes no parameters")
    print "import"
    print "marks %s" % (work_path("marks"))
#   print "export"
    print  # Terminate with a blank line
    return 0


def do_addsymbol (*args):
    """Do the 'addsymbol' command; add given CVS symbol to local cache."""
    if len(args) != 1:
        die_usage("'addsymbol' takes one parameter: symbol")
    symbol = args[0]
    progress = ProgressIndicator("    ", sys.stderr)
    if valid_cvs_symbol(symbol):
        Globals.CVSSymbolCache.sync_symbol(symbol, Globals.CVSWorkDir,
                                           progress)
        progress.finish("Added '%s' to CVS symbol cache" % (symbol), True)
    else:
        error("Skipping CVS symbol '%s'; it is not a valid git ref", symbol)
    print  # Terminate with a blank line
    return 0


def do_syncsymbols (*args):
    """Do the 'syncsymbols' command; sync all symbols with CVS server."""
    if args:
        die_usage("'syncsymbols' takes no parameters")
    progress = ProgressIndicator("    ", sys.stderr)
    Globals.CVSSymbolCache.sync_all_symbols(Config.CVSRepo, progress,
                                            valid_cvs_symbol)
    progress.finish()
    print  # Terminate with a blank line
    return 0


def do_verify (*args):
    """Do the 'verify' command; Compare CVS checkout and Git tree."""
    if len(args) != 1:
        die_usage("'verify' takes one parameter: symbol")
    symbol = args[0]
    gitref = cvs_to_refname(symbol)
    assert valid_git_ref(gitref)

    progress = ProgressIndicator("    ", sys.stderr)
    progress("Checking out '%s' from CVS..." % (symbol))
    Globals.CVSWorkDir.update(symbol)

    add_env = {"GIT_INDEX_FILE": os.path.abspath(work_path("temp_index"))}
    progress("Creating Git index from tree object @ '%s'..." % (gitref))
    cmd = ("git", "read-tree", gitref)
    assert run_command(cmd, add_env = add_env)[0] == 0

    progress("Comparing CVS checkout to Git index...", True)
    cmd = ("git", "--work-tree=%s" % (os.path.abspath(work_path("cvs"))),
           "ls-files", "--exclude=CVS", "--deleted", "--modified", "--others",
           "-t")
    exit_code, output, errors = run_command(cmd, add_env = add_env)
    assert exit_code == 0 and not errors

    if output:
        progress.finish("Failed verification of '%s'" % (symbol), True)
        error("The '%s' command returned:\n---\n%s---", " ".join(cmd), output)
    else:
        progress.finish("Successfully verified '%s'" % (symbol), True)
    print  # Terminate with a blank line
    return exit_code


def not_implemented (*args):
    """Abort, while informing user that this command is not yet implemented."""
    die_usage("Command not implemented")


COMMANDS = {
    "capabilities": do_capabilities,
    "list": do_list,
    # Special handling of 'import' in main()
    # "import": do_import,
    "export": not_implemented,
    # Custom commands
    "addsymbol": do_addsymbol,
    "syncsymbols": do_syncsymbols,
    "verify": do_verify,
}


class Globals(object):

    """Global variables are placed here at the start of main()."""

    pass


def main (*args):
    """Main program logic; execution starts here."""
    debug("Invoked '%s'", " ".join(args))

    # Initialization of subsystems
    assert len(args) >= 2
    # Read config for the given remote
    Config.init(args[1])
    # Local CVS symbol cache (CVS symbol -> CVS state mapping)
    Globals.CVSSymbolCache = CVSSymbolCache(work_path("symbols"))
    # Local CVS checkout
    Globals.CVSWorkDir = CVSWorkDir(work_path("cvs"), Config.CVSRepo)
    # Interface to 'git cat-file --batch'
    Globals.GitObjectFetcher = GitObjectFetcher()
    # Interface to Git object notes
    Globals.GitNotes = GitNotes(Config.NotesRef, Globals.GitObjectFetcher)
    # Mapping from Git commit objects to CVS states
    Globals.CommitStates = CommitStates(Globals.GitNotes)
    # Mapping from Git ref names to Git object names
    Globals.GitRefMap = GitRefMap(Globals.GitObjectFetcher)
    # Mapping from CVS revision to Git blob and commit objects
    Globals.CVSRevisionMap = CVSRevisionMap(cvs_to_refname("_metadata"),
                                            Globals.GitObjectFetcher)
    last_mark = 0
    if Globals.CVSRevisionMap.has_unresolved_marks():
        # Update with marks from last import
        last_mark = Globals.CVSRevisionMap.load_marks_file(work_path("marks"))
    else:
        # Truncate marks file.  We cannot automatically do this after
        # .load_marks_file() above, since we cannot yet guarantee that
        # we will be able to save the revision map persistently.  (That
        # can only happen if we are given one or more import commands
        # below.) We can only truncate this file when we know there are
        # no unresolved marks in the revision map.
        open(work_path("marks"), "w").close()
    # Mapping from CVS states to commit objects that contain said state
    Globals.CVSStateMap = CVSStateMap(Globals.CVSRevisionMap)

    # Main program loop
    import_refs = []  # Accumulate import commands here
    # Cannot use "for line in sys.stdin" for buffering (?) reasons
    line = sys.stdin.readline()
    while (line):
        cmdline = line.strip().split()
        if not cmdline:
            break  # Blank line means we're about to quit
        debug("Got command '%s'", " ".join(cmdline))
        cmd = cmdline.pop(0)
        if cmd == "import":
            import_refs.extend(cmdline)
        else:
            if cmd not in COMMANDS:
                die_usage("Unknown command '%s'", cmd)
            if COMMANDS[cmd](*cmdline):
                die("Command '%s' failed", line.strip())
            sys.stdout.flush()
        line = sys.stdin.readline()

    # Trigger import processing after last import command
    ret = 0
    if import_refs:
        # Init producer of output in the git-fast-import format
        Globals.GitFastImport = GitFastImport(
            sys.stdout, Globals.GitObjectFetcher, last_mark)

        # Perform import of given refs
        ret = do_import(*import_refs)

        # Notes on persistent storage of subsystems' data structures:
        #
        # Because the "import" command has been called, we here _know_
        # that there is a fast-import process running in parallel.
        # (This is NOT the case when there are no "import" commands).
        # We can therefore now (and only now) safely commit the extra
        # information that we store in the Git repo.
        # In other words, the data structures that we commit to
        # persistent storage with the following calls will NOT be
        # committed if there are no "import" commands.  The data
        # structures must handle this in one of two ways:
        # - In the no-"import" scenario, there is simply nothing to
        #   commit, so it can safely be skipped.
        # - Any information that should have been committed in the
        #   no-"import" scenario can be reconstructed repeatedly in
        #   subsequent executions of this program, until the next
        #   invocation of an "import" command provides an opportunity
        #   to commit the data structure to persistent storage.

        # Write out commit notes (mapping git commits to CVSStates)
        # The following call would be a no-op in the no-"import" case
        Globals.GitNotes.commit_notes(Globals.GitFastImport, Config.Author,
            'Annotate commits imported by "git remote-cvs"\n')

        # Save CVS revision metadata
        # This data structure can handle the no-"import" case as long
        # as the marks file from the last fast-import run is still
        # present upon the next execution of this program.
        Globals.CVSRevisionMap.commit_map(Globals.GitFastImport, Config.Author,
            'Updated metadata used by "git remote-cvs"\n')

    return ret


if __name__ == '__main__':
    sys.exit(main(*sys.argv))
