static int diff_no_prefix;
	if (!strcmp(var, "diff.noprefix")) {
		diff_no_prefix = git_config_bool(var, value);
		return 0;
	}
	struct diff_options *opt;
static void emit_line_0(struct diff_options *o, const char *set, const char *reset,
	FILE *file = o->file;

	if (o->output_prefix) {
		struct strbuf *msg = NULL;
		msg = o->output_prefix(o, o->output_prefix_data);
		assert(msg);
		fwrite(msg->buf, msg->len, 1, file);
	}
static void emit_line(struct diff_options *o, const char *set, const char *reset,
	emit_line_0(o, set, reset, line[0], line+1, len-1);
		emit_line_0(ecbdata->opt, set, reset, '+', line, len);
		emit_line_0(ecbdata->opt, ws, reset, '+', line, len);
		emit_line_0(ecbdata->opt, set, reset, '+', "", 0);
			      ecbdata->opt->file, set, reset, ws);
	struct strbuf msgbuf = STRBUF_INIT;
	int org_len = len;
	int i = 1;
		emit_line(ecbdata->opt, plain, reset, line, len);
	strbuf_add(&msgbuf, frag, strlen(frag));
	strbuf_add(&msgbuf, line, ep - line);
	strbuf_add(&msgbuf, reset, strlen(reset));

	/*
	 * trailing "\r\n"
	 */
	for ( ; i < 3; i++)
		if (line[len - i] == '\r' || line[len - i] == '\n')
			len--;
	if (ep != cp) {
		strbuf_add(&msgbuf, plain, strlen(plain));
		strbuf_add(&msgbuf, cp, ep - cp);
		strbuf_add(&msgbuf, reset, strlen(reset));
	}
	if (ep < line + len) {
		strbuf_add(&msgbuf, func, strlen(func));
		strbuf_add(&msgbuf, ep, line + len - ep);
		strbuf_add(&msgbuf, reset, strlen(reset));
	}

	strbuf_add(&msgbuf, line + len, org_len - len);
	emit_line(ecbdata->opt, "", "", msgbuf.buf, msgbuf.len);
	strbuf_release(&msgbuf);
			emit_line_0(ecb->opt, old, reset, '-',
		emit_line_0(ecb->opt, plain, reset, '\\',
	char *line_prefix = "";
	struct strbuf *msgbuf;

	if (o && o->output_prefix) {
		msgbuf = o->output_prefix(o, o->output_prefix_data);
		line_prefix = msgbuf->buf;
	}
	ecbdata.opt = o;
		"%s%s--- %s%s%s\n%s%s+++ %s%s%s\n%s%s@@ -",
		line_prefix, metainfo, a_name.buf, name_a_tab, reset,
		line_prefix, metainfo, b_name.buf, name_b_tab, reset,
		line_prefix, fraginfo);
	int last_minus;
	struct diff_options *opt;
					  size_t count, const char *buf,
					  const char *line_prefix)
	int print = 0;

		if (print)
			fputs(line_prefix, fp);
		print = 1;
/*
 * '--color-words' algorithm can be described as:
 *
 *   1. collect a the minus/plus lines of a diff hunk, divided into
 *      minus-lines and plus-lines;
 *
 *   2. break both minus-lines and plus-lines into words and
 *      place them into two mmfile_t with one word for each line;
 *
 *   3. use xdiff to run diff on the two mmfile_t to get the words level diff;
 *
 * And for the common parts of the both file, we output the plus side text.
 * diff_words->current_plus is used to trace the current position of the plus file
 * which printed. diff_words->last_minus is used to trace the last minus word
 * printed.
 *
 * For '--graph' to work with '--color-words', we need to output the graph prefix
 * on each line of color words output. Generally, there are two conditions on
 * which we should output the prefix.
 *
 *   1. diff_words->last_minus == 0 &&
 *      diff_words->current_plus == diff_words->plus.text.ptr
 *
 *      that is: the plus text must start as a new line, and if there is no minus
 *      word printed, a graph prefix must be printed.
 *
 *   2. diff_words->current_plus > diff_words->plus.text.ptr &&
 *      *(diff_words->current_plus - 1) == '\n'
 *
 *      that is: a graph prefix must be printed following a '\n'
 */
static int color_words_output_graph_prefix(struct diff_words_data *diff_words)
{
	if ((diff_words->last_minus == 0 &&
		diff_words->current_plus == diff_words->plus.text.ptr) ||
		(diff_words->current_plus > diff_words->plus.text.ptr &&
		*(diff_words->current_plus - 1) == '\n')) {
		return 1;
	} else {
		return 0;
	}
}

	struct diff_options *opt = diff_words->opt;
	struct strbuf *msgbuf;
	char *line_prefix = "";
	assert(opt);
	if (opt->output_prefix) {
		msgbuf = opt->output_prefix(opt, opt->output_prefix_data);
		line_prefix = msgbuf->buf;
	}

	if (color_words_output_graph_prefix(diff_words)) {
		fputs(line_prefix, diff_words->opt->file);
	}
	if (diff_words->current_plus != plus_begin) {
		fn_out_diff_words_write_helper(diff_words->opt->file,
				diff_words->current_plus, line_prefix);
		if (*(plus_begin - 1) == '\n')
			fputs(line_prefix, diff_words->opt->file);
	}
	if (minus_begin != minus_end) {
		fn_out_diff_words_write_helper(diff_words->opt->file,
				minus_end - minus_begin, minus_begin,
				line_prefix);
	}
	if (plus_begin != plus_end) {
		fn_out_diff_words_write_helper(diff_words->opt->file,
				plus_end - plus_begin, plus_begin,
				line_prefix);
	}
	diff_words->last_minus = minus_first;
	struct diff_options *opt = diff_words->opt;
	struct strbuf *msgbuf;
	char *line_prefix = "";

	assert(opt);
	if (opt->output_prefix) {
		msgbuf = opt->output_prefix(opt, opt->output_prefix_data);
		line_prefix = msgbuf->buf;
	}

		fputs(line_prefix, diff_words->opt->file);
		fn_out_diff_words_write_helper(diff_words->opt->file,
			diff_words->minus.text.size,
			diff_words->minus.text.ptr, line_prefix);
	diff_words->last_minus = 0;
			diff_words->plus.text.size) {
		if (color_words_output_graph_prefix(diff_words))
			fputs(line_prefix, diff_words->opt->file);
		fn_out_diff_words_write_helper(diff_words->opt->file,
			- diff_words->current_plus, diff_words->current_plus,
			line_prefix);
	}
	struct diff_options *o = ecbdata->opt;
	char *line_prefix = "";
	struct strbuf *msgbuf;

	if (o && o->output_prefix) {
		msgbuf = o->output_prefix(o, o->output_prefix_data);
		line_prefix = msgbuf->buf;
	}
		fprintf(ecbdata->opt->file, "%s", ecbdata->header->buf);
		fprintf(ecbdata->opt->file, "%s%s--- %s%s%s\n",
			line_prefix, meta, ecbdata->label_path[0], reset, name_a_tab);
		fprintf(ecbdata->opt->file, "%s%s+++ %s%s%s\n",
			line_prefix, meta, ecbdata->label_path[1], reset, name_b_tab);
			putc('\n', ecbdata->opt->file);
		emit_line(ecbdata->opt, reset, reset, line, len);
			fputs("~\n", ecbdata->opt->file);
			emit_line(ecbdata->opt, plain, reset, line, len);
			fputs("~\n", ecbdata->opt->file);
			emit_line(ecbdata->opt, plain, reset, line+1, len-1);
		emit_line(ecbdata->opt, color, reset, line, len);
	const char *line_prefix = "";
	struct strbuf *msg = NULL;
	if (options->output_prefix) {
		msg = options->output_prefix(options, options->output_prefix_data);
		line_prefix = msg->buf;
	}

			fprintf(options->file, "%s", line_prefix);
			fprintf(options->file, "%s", line_prefix);
		fprintf(options->file, "%s", line_prefix);
	fprintf(options->file, "%s", line_prefix);
	if (options->output_prefix) {
		struct strbuf *msg = NULL;
		msg = options->output_prefix(options,
				options->output_prefix_data);
		fprintf(options->file, "%s", msg->buf);
	}
		if (options->output_prefix) {
			struct strbuf *msg = NULL;
			msg = options->output_prefix(options,
					options->output_prefix_data);
			fprintf(options->file, "%s", msg->buf);
		}

static long gather_dirstat(struct diff_options *opt, struct dirstat_dir *dir,
		unsigned long changed, const char *base, int baselen)
	const char *line_prefix = "";
	struct strbuf *msg = NULL;

	if (opt->output_prefix) {
		msg = opt->output_prefix(opt, opt->output_prefix_data);
		line_prefix = msg->buf;
	}
			this = gather_dirstat(opt, dir, changed, f->name, newbaselen);
				fprintf(opt->file, "%s%4d.%01d%% %.*s\n", line_prefix,
					percent, permille % 10, baselen, base);
	gather_dirstat(options, &dir, changed, "", 0);
	char *line_prefix = "";
	struct strbuf *msgbuf;

	assert(data->o);
	if (data->o->output_prefix) {
		msgbuf = data->o->output_prefix(data->o,
			data->o->output_prefix_data);
		line_prefix = msgbuf->buf;
	}
				"%s%s:%d: leftover conflict marker\n",
				line_prefix, data->filename, data->lineno);
		fprintf(data->o->file, "%s%s:%d: %s.\n",
			line_prefix, data->filename, data->lineno, err);
		emit_line(data->o, set, reset, line, 1);
static void emit_binary_diff_body(FILE *file, mmfile_t *one, mmfile_t *two, char *prefix)
		fprintf(file, "%sdelta %lu\n", prefix, orig_size);
		fprintf(file, "%sliteral %lu\n", prefix, two->size);
		fprintf(file, "%s", prefix);
	fprintf(file, "%s\n", prefix);
static void emit_binary_diff(FILE *file, mmfile_t *one, mmfile_t *two, char *prefix)
	fprintf(file, "%sGIT binary patch\n", prefix);
	emit_binary_diff_body(file, one, two, prefix);
	emit_binary_diff_body(file, two, one, prefix);
			 int must_show_header,
	struct strbuf *msgbuf;
	char *line_prefix = "";

	if (o->output_prefix) {
		msgbuf = o->output_prefix(o, o->output_prefix_data);
		line_prefix = msgbuf->buf;
	}
	strbuf_addf(&header, "%s%sdiff --git %s %s%s\n", line_prefix, set, a_one, b_two, reset);
		strbuf_addf(&header, "%s%snew file mode %06o%s\n", line_prefix, set, two->mode, reset);
		must_show_header = 1;
		strbuf_addf(&header, "%s%sdeleted file mode %06o%s\n", line_prefix, set, one->mode, reset);
		must_show_header = 1;
			strbuf_addf(&header, "%s%sold mode %06o%s\n", line_prefix, set, one->mode, reset);
			strbuf_addf(&header, "%s%snew mode %06o%s\n", line_prefix, set, two->mode, reset);
			must_show_header = 1;
		    !memcmp(mf1.ptr, mf2.ptr, mf1.size)) {
			if (must_show_header)
				fprintf(o->file, "%s", header.buf);
		}
			emit_binary_diff(o->file, &mf1, &mf2, line_prefix);
			fprintf(o->file, "%sBinary files %s and %s differ\n",
				line_prefix, lbl[0], lbl[1]);
		if (!DIFF_XDL_TST(o, WHITESPACE_FLAGS) || must_show_header) {
		ecbdata.opt = o;
			ecbdata.diff_words->opt = o;
			  int *must_show_header,
	struct strbuf *msgbuf;
	char *line_prefix = "";
	*must_show_header = 1;
	if (o->output_prefix) {
		msgbuf = o->output_prefix(o, o->output_prefix_data);
		line_prefix = msgbuf->buf;
	}
		strbuf_addf(msg, "%s%ssimilarity index %d%%",
			    line_prefix, set, similarity_index(p));
		strbuf_addf(msg, "%s\n%s%scopy from ",
			    reset,  line_prefix, set);
		strbuf_addf(msg, "%s\n%s%scopy to ", reset, line_prefix, set);
		strbuf_addf(msg, "%s%ssimilarity index %d%%",
			    line_prefix, set, similarity_index(p));
		strbuf_addf(msg, "%s\n%s%srename from ",
			    reset, line_prefix, set);
		strbuf_addf(msg, "%s\n%s%srename to ",
			    reset, line_prefix, set);
			strbuf_addf(msg, "%s%sdissimilarity index %d%%%s\n",
				    line_prefix,
		*must_show_header = 0;
		strbuf_addf(msg, "%s%sindex %s..", set,
			    line_prefix,
			    find_unique_abbrev(one->sha1, abbrev));
		strbuf_addstr(msg, find_unique_abbrev(two->sha1, abbrev));
	int must_show_header = 0;
			      &must_show_header,
			     one, two, xfrm_msg, must_show_header,
			     o, complete_rewrite);
	if (diff_no_prefix) {
		options->a_prefix = options->b_prefix = "";
	} else if (!diff_mnemonic_prefix) {
	if (opt->output_prefix) {
		struct strbuf *msg = NULL;
		msg = opt->output_prefix(opt, opt->output_prefix_data);
		fprintf(opt->file, "%s", msg->buf);
	}
static void show_mode_change(FILE *file, struct diff_filepair *p, int show_name,
		const char *line_prefix)
		fprintf(file, "%s mode change %06o => %06o%c", line_prefix, p->one->mode,
			p->two->mode, show_name ? ' ' : '\n');
static void show_rename_copy(FILE *file, const char *renamecopy, struct diff_filepair *p,
			const char *line_prefix)
	show_mode_change(file, p, 0, line_prefix);
static void diff_summary(struct diff_options *opt, struct diff_filepair *p)
	FILE *file = opt->file;
	char *line_prefix = "";

	if (opt->output_prefix) {
		struct strbuf *buf = opt->output_prefix(opt, opt->output_prefix_data);
		line_prefix = buf->buf;
	}

		fputs(line_prefix, file);
		fputs(line_prefix, file);
		fputs(line_prefix, file);
		show_rename_copy(file, "copy", p, line_prefix);
		fputs(line_prefix, file);
		show_rename_copy(file, "rename", p, line_prefix);
			fprintf(file, "%s rewrite ", line_prefix);
		show_mode_change(file, p, !p->score, line_prefix);
		for (i = 0; i < q->nr; i++) {
			diff_summary(options, q->queue[i]);
		}