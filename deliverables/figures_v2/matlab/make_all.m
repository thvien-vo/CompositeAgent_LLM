function make_all(names)
%MAKE_ALL Regenerates all MATLAB figures from the stored result files. Nothing is recomputed.
%   Usage: cd to this folder, then   make_all            all figures
%                                    make_all("Fig3")     only this one
%   The PDF files are written to _raw at 1.5 times the size; postprocess.py scales them to the journal size and
%   makes the PNG files.

here = fileparts(mfilename('fullpath'));
rawdir = fullfile(here, '_raw');
if ~exist(rawdir, 'dir'), mkdir(rawdir); end
S = style_setup();
d = load_data(here);
all_names = ["Fig1" "Fig2" "Fig3" "Fig4" "Fig5" "FigS1" "FigS2" "FigS3" "FigS4" "FigS5"];
if nargin < 1, names = all_names; end
reports = {};
for nm = string(names)
    fn = str2func("fig_" + nm);
    r = fn(d, S, S.paper, rawdir);
    reports = [reports r]; %#ok<AGROW>
    if any(nm == ["Fig1" "Fig2" "Fig3" "Fig4" "Fig5"])
        r = fn(d, S, S.slide, rawdir);
        reports = [reports r]; %#ok<AGROW>
    end
    fprintf('%s done\n', nm);
end
path = fullfile(here, '_report_matlab.json');
old = {};
if isfile(path)
    prev = jsondecode(fileread(path));
    if iscell(prev), old = prev(:)'; else, old = num2cell(prev(:)'); end
end
keep = true(size(old));
for i = 1:numel(old)
    for j = 1:numel(reports)
        if strcmp(old{i}.name, reports{j}.name) && strcmp(old{i}.mode, reports{j}.mode), keep(i) = false; end
    end
end
fid = fopen(path, 'w', 'n', 'UTF-8');
fwrite(fid, jsonencode([old(keep) reports]), 'char');
fclose(fid);
n = 0;
for i = 1:numel(reports)
    r = reports{i};
    fprintf('%s %s collisions %d colours %d\n', r.name, r.mode, numel(r.collisions), numel(r.colours));
    n = n + numel(r.collisions) + numel(r.colours);
    for j = 1:min(6, numel(r.collisions)), fprintf('   %s\n', r.collisions{j}); end
    for j = 1:min(6, numel(r.colours)), fprintf('   %s\n', r.colours{j}); end
end
fprintf('problems: %d\n', n);
py = fullfile(here, '..', '..', '..', 'venv_fig', 'Scripts', 'python.exe');
if isfile(py)
    [status, out] = system(sprintf('"%s" "%s"', py, fullfile(here, 'postprocess.py')));
    fprintf('%s', out);
    if status ~= 0, error('postprocess.py failed'); end
else
    fprintf('venv_fig not found: PDF files stay in _raw at 1.5 times the size\n');
end
end

% ---------------------------------------------------------------------------------------------------- data
function d = load_data(here)
root = fullfile(here, '..', '..', '..');
res = fullfile(root, 'deliverables', 'optimization', 'results');
opts = {'TextType', 'string', 'VariableNamingRule', 'preserve', 'Delimiter', ','};
t = readtable(fullfile(res, 'cases_summary.csv'), opts{:});
d.T = t(t.model == "ritz_full", :);
d.ids = unique(d.T.("case"), 'stable')';
o = readtable(fullfile(res, 'before_ritz', 'cases_summary.csv'), opts{:});
d.O = o(o.model == "closed_form", :);
d.LH = readtable(fullfile(res, 'leriche_haftka_summary.csv'), opts{:});
d.F = jsondecode(fileread(fullfile(res, 'fronts.json')));
d.R = jsondecode(fileread(fullfile(res, 'runs_history.json')));
d.H = jsondecode(fileread(fullfile(res, 'leriche_haftka_histories.json')));
m = jsondecode(fileread(fullfile(res, 'run_cases_meta.json')));
d.budget = m.budget;
d.seeds = numel(m.seeds);
txt = fileread(fullfile(root, 'python', 'optimization', 'experiments', 'cases.py'));
tok = regexp(txt, 'SAFETY_FACTOR = ([\d.]+)', 'tokens', 'once');
d.sf = str2double(tok{1});
d.nmax = 0;
fn = fieldnames(d.F);
for i = 1:numel(fn)
    d.nmax = max(d.nmax, max([d.F.(fn{i}).bounds.n]));
end
end

function r = row(T, c, tk)
r = T(T.("case") == c & T.thickness == tk, :);
end

function tf = feasible(r)
tf = strcmpi(string(r.feasible), "true");
end

function tf = proven(r)
tf = any(r.exact_status == ["optimal" "infeasible"]);
end

function v = half_up(x)
v = floor(x + 0.5);
end

function g = grid(W, H, left, right, bottom, top, gapx, gapy, rows, cols)
w = (W - left - right - (cols - 1) * gapx) / cols;
h = (H - bottom - top - (rows - 1) * gapy) / rows;
g = cell(rows, cols);
for r = 0:rows - 1
    for c = 0:cols - 1
        g{r + 1, c + 1} = [left + c * (w + gapx), H - top - (r + 1) * h - r * gapy, w, h];
    end
end
end

function x = axis_start(first_hit)
x = first_hit * 0.8;
e = 10 ^ floor(log10(x));
x = floor(x / e) * e;
end

function [xs, ys] = ecdf_xy(hits, n_runs, x0, x1)
hits = sort(hits(:))';
m = numel(hits);
xs = [x0 reshape([hits; hits], 1, []) x1];
ys = [0 0 reshape(repmat((1:m) * 100 / n_runs, 2, 1), 1, [])];
ys = ys(1:numel(xs));
end

function txt = num_labels(v)
txt = arrayfun(@(a) sprintf('%g', a), v, 'UniformOutput', false);
end

function out = prct(v, q)
% linear interpolation between order statistics, column by column (same definition as numpy.percentile)
v = sort(v, 1);
n = size(v, 1);
pos = (n - 1) * q / 100 + 1;
lo = floor(pos); hi = ceil(pos);
out = v(lo, :) + (pos - lo) * (v(hi, :) - v(lo, :));
end

function txt = saving_tex(v)
txt = sprintf('$-%d\\%%$', half_up(v));
end

% ---------------------------------------------------------------------------------------------------- Fig1
function T = text_paper()
T.request = {'Request in words', '(English or Vietnamese)'};
T.router = {'Router: Python rules first,', 'LLM confirms weak design wording'};
T.refused = {'Refused with a hint', '(unclear or contradictory text)'};
T.a_read = {'LLM copies numbers and units', 'into a fixed JSON schema'};
T.a_chk = {'Python checks every value against', 'the text; one retry, else refused'};
T.d_read = {'LLM copies the request', 'into a fixed JSON schema'};
T.d_chk = {'Python re-reads the text: the text', 'wins; defaults are printed'};
T.q_vec = {'Question turned into a vector', '(nomic-embed-text)'};
T.q_ret = {'Retrieval from the material data:', 'cosine similarity + exact name match'};
T.ply = {'Ply properties: measured values when one known material system is named,', ...
    'else ML (random forest) prediction for the fibre group'};
T.q_prompt = {'Prompt built from the best rows', 'and a ranking computed by Python'};
T.clt = {'CLT in MATLAB: ABD matrix, ply', 'stresses, Max Stress failure index'};
T.opt = {'Optimiser: exact search; if it', 'cannot finish, GA + local search'};
T.final = {'Final design checked: MATLAB strength,', 'polynomial Ritz, quasi-isotropic laminate'};
T.a_llm = {'LLM explains the numbers'};
T.d_llm = {'LLM explains the design'};
T.q_llm = {'LLM answers and cites report and page'};
T.a_guard = {'Every number must be in the data and', 'named correctly; else pre-built text'};
T.d_guard = T.a_guard;
T.q_guard = {'Numbers and report ids must be in', 'the rows; else pre-built text'};
T.out = {'Result, with an explanation or answer that passed the guard'};
end

function T = text_slide()
T.request = {'Request in words'}; T.router = {'Router: Python rules, LLM confirms'};
T.refused = {'Refused with a hint'}; T.a_read = {'LLM copies numbers, units'}; T.a_chk = {'Python checks against text'};
T.d_read = {'LLM copies the request'}; T.d_chk = {'Python re-reads the text'}; T.q_vec = {'Question to vector'};
T.q_ret = {'Retrieval from material data'}; T.ply = {'Ply properties: measured values, else ML prediction'};
T.q_prompt = {'Prompt from best rows'}; T.clt = {'CLT in MATLAB'}; T.opt = {'Exact search, else GA + LS'};
T.final = {'MATLAB, Ritz, quasi-isotropic'}; T.a_llm = {'LLM explains the numbers'}; T.d_llm = {'LLM explains the design'};
T.q_llm = {'LLM answers, cites source'}; T.a_guard = {'Numbers checked against data'};
T.d_guard = T.a_guard; T.q_guard = {'Numbers checked against rows'};
T.out = {'Result, with a verified explanation or answer'};
end

function r = fig_Fig1(~, S, s, rawdir)
paper = strcmp(s.mode, 'paper');
if paper
    W = 190; H = 131; T = text_paper(); gap_c = 4; mx = 0.6; key_y = H - 2.8; h1 = 10.5; h2 = 7; g = 3.6;
    y = H - 7; first = 8.5; hl = h2; bus_d = 2.6; lab_x = 1.2; lab_y = 1.4;
    kinds = {'llm', 24; 'data', 36; 'comp', 37; 'check', 28};
else
    W = S.slide_W; H = S.slide_H; T = text_slide(); gap_c = 6; mx = 1.2; key_y = H - 5.5; h1 = 14.6; h2 = 14.6; g = 4.9;
    y = H - 11; first = 12.5; hl = h1; bus_d = 3.4; lab_x = 2.4; lab_y = 2.8;
    kinds = {'llm', 46; 'data', 82; 'comp', 88; 'check', 60};
end
p = Page('Fig1_workflow', W, H, s, S);
cw = (W - 2 * gap_c - 2 * mx) / 3;
cx = mx + (0:2) * (cw + gap_c);
mid = cx + cw / 2;
list = {'top', h1, first; 'read', h1, g; 'chk', h1, g; 'data', h1, g; 'comp', h1, g; 'final', h1, g; 'llm', hl, g; ...
    'guard', h1, g; 'out', h2, 0};
rows = struct();
for i = 1:size(list, 1)
    rows.(list{i, 1}) = [y - list{i, 2}, list{i, 2}];
    y = y - list{i, 2} - list{i, 3};
end
x = mx;
hk = s.legend * 25.4 / 72;
for i = 1:size(kinds, 1)
    p.block(x, key_y - hk / 2, s.sample, hk, {}, kinds{i, 1});
    p.text(x + s.sample + 1.5, key_y, S.block_name.(kinds{i, 1}), s.legend, 'ha', 'left');
    x = x + kinds{i, 2};
end
    function blk(col, rowname, key, kind, span)
        if nargin < 5, span = 1; end
        q = rows.(rowname);
        p.block(cx(col), q(1), cw * span + gap_c * (span - 1), q(2), T.(key), kind);
    end
    function down(col, r0, r1)
        a = rows.(r0); b = rows.(r1);
        p.arrow([mid(col) a(1)], [mid(col) b(1) + b(2)]);
    end
blk(1, 'top', 'request', 'none');
blk(2, 'top', 'router', 'check');
blk(3, 'top', 'refused', 'none');
q = rows.top;
p.arrow([cx(1) + cw, q(1) + q(2) / 2], [cx(2), q(1) + q(2) / 2]);
p.arrow([cx(2) + cw, q(1) + q(2) / 2], [cx(3), q(1) + q(2) / 2]);
bus = q(1) - bus_d;
p.wire([mid(2) q(1)], [mid(2) bus]);
p.wire([mid(1) bus], [mid(3) bus]);
labs = {'Analysis', 'Design', 'Question'};
for i = 1:3
    p.arrow([mid(i) bus], [mid(i) rows.read(1) + rows.read(2)]);
    p.text(mid(i) + lab_x, bus - lab_y, labs{i}, s.block, 'ha', 'left', 'va', 'top');
end
blk(1, 'read', 'a_read', 'llm'); blk(2, 'read', 'd_read', 'llm'); blk(3, 'read', 'q_vec', 'data');
blk(1, 'chk', 'a_chk', 'check'); blk(2, 'chk', 'd_chk', 'check'); blk(3, 'chk', 'q_ret', 'data');
blk(1, 'data', 'ply', 'data', 2); blk(3, 'data', 'q_prompt', 'data');
blk(1, 'comp', 'clt', 'comp'); blk(2, 'comp', 'opt', 'comp');
blk(2, 'final', 'final', 'check');
blk(1, 'llm', 'a_llm', 'llm'); blk(2, 'llm', 'd_llm', 'llm'); blk(3, 'llm', 'q_llm', 'llm');
blk(1, 'guard', 'a_guard', 'check'); blk(2, 'guard', 'd_guard', 'check'); blk(3, 'guard', 'q_guard', 'check');
blk(1, 'out', 'out', 'none', 3);
for c = 1:3
    down(c, 'read', 'chk'); down(c, 'chk', 'data'); down(c, 'llm', 'guard'); down(c, 'guard', 'out');
end
down(1, 'data', 'comp'); down(2, 'data', 'comp'); down(1, 'comp', 'llm'); down(2, 'comp', 'final');
down(2, 'final', 'llm'); down(3, 'data', 'llm');
r = {p.save(rawdir)};
end

% ---------------------------------------------------------------------------------------------------- Fig2
function r = fig_Fig2(d, S, s, rawdir)
paper = strcmp(s.mode, 'paper');
if paper
    W = 140; H = 84; box = [13 11 W - 17 H - 20]; xl_y = 1.2; yl_x = 3.4; y = H - 4; xs = [13 29 45 61 80 101];
else
    W = S.slide_W; H = S.slide_H; box = [28 22 W - 36 H - 41]; xl_y = 3; yl_x = 10; y = H - 8; xs = [28 66 104 142 184 234];
end
p = Page('Fig2_leriche_haftka', W, H, s, S);
cases = ["LH-A" "LH-B" "LH-C" "LH-D"];
roles = {'LHA', 'LHB', 'LHC', 'LHD'};
marks = {'o', 's', '^', 'd'};
hits = cell(4, 2); runs = zeros(4, 2);
first = inf;
for i = 1:4
    q = d.H.(strrep(char(cases(i)), '-', '_')).runs;
    for j = 1:2
        rr = q([q.local_search] == (j == 2));
        h = [rr.hit_evals];
        col = "ga_exact_hits"; if j == 2, col = "ga_ls_exact_hits"; end
        if numel(h) ~= d.LH.(col)(i), error('history and summary disagree'); end
        hits{i, j} = h; runs(i, j) = numel(rr);
        first = min(first, min(h));
    end
end
x1 = d.LH.ga_budget(1);
x0 = axis_start(first);
ticks = [100 300 1000 3000 x1];
a = p.axes(box, [x0 x1], [0 104], 'xlog', true, 'xticks', ticks, 'yticks', [0 25 50 75 100], ...
    'xlabels', num_labels(ticks), 'ylabels', {'0', '25', '50', '75', '100'});
for i = 1:4
    c = S.role.(roles{i});
    for j = 1:2
        [xx, yy] = ecdf_xy(hits{i, j}, runs(i, j), x0, x1);
        xx = min(xx, x1);
        if j == 1
            ls = '--'; lab = cases(i) + " GA"; mfc = S.WHITE;
        else
            ls = '-'; lab = cases(i) + " GA + LS"; mfc = c;
        end
        p.line(a, xx, yy, roles{i}, 'ls', ls, 'marker', marks{i}, 'every', [2 8], 'mfc', mfc, 'mew', s.mew * 1.6, ...
            'label', char(lab));
    end
end
p.xlabel(a, 'Distinct designs evaluated', xl_y);
p.ylabel(a, 'Runs at the exact optimum (\%)', yl_x);
for i = 1:4
    p.key_line(xs(i), y, roles{i}, char(cases(i)), 'ls', 'none', 'marker', marks{i});
end
p.key_line(xs(5), y, 'exact', 'GA', 'ls', '--');
p.key_line(xs(6), y, 'exact', 'GA + LS', 'ls', '-');
r = {p.save(rawdir)};
end

% ---------------------------------------------------------------------------------------------------- Fig3
function pts = nsga_points(fr)
if iscell(fr)
    pts = cell2mat(cellfun(@(c) reshape(c, [], 2), fr(:), 'UniformOutput', false));
else
    pts = reshape(fr, [], 2);
end
end

function pareto_panel(d, p, a, c)
s = p.s;
tks = ["t0125" "t0183"];
p.hline(a, d.sf);
for tk = tks
    f = d.F.(sprintf('%s_%s_ritz_full', c, tk));
    p.line(a, [f.true_front.n], [f.true_front.margin], char(tk), 'marker', p.S.thick_mark.(char(tk)), 'ms', s.ms * 0.9, ...
        'label', sprintf('%s %s exact', c, tk));
end
for tk = tks
    f = d.F.(sprintf('%s_%s_ritz_full', c, tk));
    q = nsga_points(f.nsga2_fronts);
    q = unique(q(q(:, 2) < 0.985 * a.yl(2), :), 'rows');
    p.line(a, q(:, 1), q(:, 2), 'seed', 'ls', 'none', 'marker', 'o', 'ms', s.ms_small, 'mfc', 'none', 'mew', s.mew, ...
        'label', sprintf('%s %s NSGA-II', c, tk));
end
for tk = tks
    q = row(d.T, c, tk);
    if feasible(q)
        p.line(a, q.n_opt, q.margin_opt, 'exact', 'ls', 'none', 'marker', 'd', 'ms', s.ms * 1.1, ...
            'label', sprintf('%s %s optimum', c, tk));
    end
end
p.text(a.box(1) + a.box(3), p.Y(a, d.sf) + 1.9 * s.pad, sprintf('$RF_{\\min} = %g$', d.sf), s.ref, 'ha', 'right', 'va', 'bottom');
end

function rep = pareto_page(d, S, s, rawdir, name, cases)
paper = strcmp(s.mode, 'paper');
if paper
    W = 190; H = 128; g = grid(W, H, 13, 2, 11, 12.5, 7, 9, 2, 2); xl_y = 1.2; yl_x = 3.4;
    xs = [13 49 85 125]; ky = H - 3.5;
else
    W = S.slide_W; H = S.slide_H; g = grid(W, H, 28, 5, 22, 24, 12, 14, 2, 2); xl_y = 3; yl_x = 10;
    xs = [28 100 172 257]; ky = H - 8;
end
p = Page(name, W, H, s, S);
xt = [10 20 30 40 50 60]; yt = [0 2 4 6 8];
axs = cell(1, 4);
for i = 1:4
    r0 = floor((i - 1) / 2) + 1; q = mod(i - 1, 2) + 1;
    xl = {}; yl = {};
    if r0 == 2, xl = num_labels(xt); end
    if q == 1, yl = num_labels(yt); end
    a = p.axes(g{r0, q}, [6 66], [0 8], 'xticks', xt, 'yticks', yt, 'xlabels', xl, 'ylabels', yl);
    c = cases(i);
    pareto_panel(d, p, a, c);
    nm = row(d.T, c, "t0125").name_en;
    p.panel(a, char('a' + i - 1), char(c + " " + nm));
    axs{i} = a;
end
p.xlabel(axs{3}, 'Number of plies, $n$', xl_y);
p.xlabel(axs{4}, 'Number of plies, $n$', xl_y);
p.ylabel(axs{1}, '$RF_{\min}$', yl_x);
p.ylabel(axs{3}, '$RF_{\min}$', yl_x);
p.key_line(xs(1), ky, 't0125', S.thick_text.t0125, 'marker', 'o', 'ms', s.ms * 0.9);
p.key_line(xs(2), ky, 't0183', S.thick_text.t0183, 'marker', 's', 'ms', s.ms * 0.9);
p.key_line(xs(3), ky, 'seed', 'NSGA-II, each seed', 'ls', 'none', 'marker', 'o', 'ms', s.ms_small, 'mfc', 'none');
p.key_line(xs(4), ky, 'exact', 'Optimum', 'ls', 'none', 'marker', 'd', 'ms', s.ms * 1.1);
rep = p.save(rawdir);
end

function r = fig_Fig3(d, S, s, rawdir)
r = {pareto_page(d, S, s, rawdir, 'Fig3_pareto', ["C1" "C4" "C5" "C7"])};
end

function r = fig_FigS1(d, S, s, rawdir)
r = {pareto_page(d, S, s, rawdir, 'FigS1_pareto_all_C1_C4', d.ids(1:4)), ...
    pareto_page(d, S, s, rawdir, 'FigS1_pareto_all_C5_C8', d.ids(5:8))};
end

% ---------------------------------------------------------------------------------------------------- Fig4
function a = qi_axes(d, p, box, tk, left)
s = p.s;
yt = [0 25 50 75 100];
top = max(d.T.qi_n) * 1.1;
n = numel(d.ids);
yl = {}; if left, yl = num_labels(yt); end
a = p.axes(box, [0.4 n + 0.6], [0 top], 'yticks', yt, 'ylabels', yl);
y1 = box(2) - s.ticklen - s.pad;
y2 = y1 - s.tick * 25.4 / 72 * 1.28;
w = 0.38; gap = 0.015;
for i = 1:n
    c = d.ids(i);
    q = row(d.T, c, tk);
    xm = p.X(a, i);
    p.text(xm, y1, char(c), s.tick, 'va', 'top');
    if isnan(q.mass_reduction_pct), lab = 'n/a'; else, lab = saving_tex(q.mass_reduction_pct); end
    p.text(xm, y2, lab, s.tick, 'va', 'top');
    xa = i - w - gap; xb = i - gap;
    p.bar(a, xa, xb, q.qi_n, 'qi', 's');
    p.text(p.X(a, (xa + xb) / 2), p.Y(a, q.qi_n) + s.pad * 0.9, sprintf('%d', q.qi_n), s.barnum, 'va', 'bottom');
    xa = i + gap; xb = i + gap + w;
    if feasible(q)
        p.bar(a, xa, xb, q.n_opt, 'opt', 'o');
        p.text(p.X(a, (xa + xb) / 2), p.Y(a, q.n_opt) + s.pad * 0.9, sprintf('%d', q.n_opt), s.barnum, 'va', 'bottom');
    else
        p.hatch_bar(a, xa, xb, d.nmax, 'opt');
        p.text(p.X(a, xa), p.Y(a, d.nmax) + s.pad * 0.9, sprintf('${>}%d$', d.nmax), s.barnum, 'ha', 'left', 'va', 'bottom');
    end
end
p.hline(a, d.nmax);
p.text(box(1) + 0.8, p.Y(a, d.nmax) + s.pad * 1.9, sprintf('Ply limit (%d)', d.nmax), s.legend, 'ha', 'left', 'va', 'bottom');
end

function fig4_key(p, xs, y)
p.key_bar(xs(1), y, 'qi', 'Quasi-isotropic', 's');
p.key_bar(xs(2), y, 'opt', 'Optimised laminate', 'o');
p.key_bar(xs(3), y, 'opt', 'No feasible design', '', true);
end

function r = fig_Fig4(d, S, s, rawdir)
tks = ["t0125" "t0183"];
ylab = sprintf('Plies needed for $RF_{\\min} \\geq %g$', d.sf);
if strcmp(s.mode, 'paper')
    W = 190; H = 88;
    p = Page('Fig4_qi_comparison', W, H, s, S);
    g = grid(W, H, 13, 2, 15, 12.5, 6, 0, 1, 2);
    for i = 1:2
        a = qi_axes(d, p, g{1, i}, tks(i), i == 1);
        p.panel(a, char('a' + i - 1), S.thick_text.(char(tks(i))));
        p.xlabel(a, 'Load case and mass saving', 1.2);
        if i == 1, p.ylabel(a, ylab, 3.4); end
    end
    fig4_key(p, [13 50 94], H - 3.5);
    r = {p.save(rawdir)};
    return
end
r = {};
for tk = tks
    W = S.slide_W; H = S.slide_H;
    p = Page(char("Fig4_qi_comparison_" + tk), W, H, s, S);
    a = qi_axes(d, p, [28 33 W - 33 H - 57], tk, true);
    p.xlabel(a, 'Load case and mass saving', 3);
    p.ylabel(a, ylab, 10);
    fig4_key(p, [28 105 195], H - 8);
    p.text(W - 5, H - 8, S.thick_text.(char(tk)), s.legend, 'ha', 'right');
    r{end + 1} = p.save(rawdir); %#ok<AGROW>
end
end

% ---------------------------------------------------------------------------------------------------- Fig5
function [hits, runs, med] = conv_cell(d, c, tk, pre)
q = row(d.T, c, tk);
if proven(q), col = pre + "_success"; else, col = pre + "_reach_reference"; end
hits = q.(col); runs = q.(pre + "_runs"); med = q.(pre + "_evals_to_hit_median");
end

function a = algo_axes(d, p, box, tk, ticks)
s = p.s;
yt = [0 5 10 15 20];
n = numel(d.ids);
xl = {}; if ticks, xl = cellstr(d.ids); end
a = p.axes(box, [0.45 n + 0.55], [0 d.seeds * 1.18], 'xticks', 1:n, 'yticks', yt, 'xlabels', xl, 'ylabels', num_labels(yt));
w = 0.27; gap = 0.012;
algos = {'GA', 'ga', 's'; 'NSGA', 'nsga2', 'd'; 'GALS', 'ga_ls', 'o'};
names = {'GA', 'NSGA-II', 'GA + LS'};
for i = 1:n
    for j = 0:2
        hits = conv_cell(d, d.ids(i), tk, string(algos{j + 1, 2}));
        xa = i + (j - 1.5) * w + (j - 1) * gap;
        xb = xa + w;
        if hits > 0
            p.bar(a, xa, xb, hits, algos{j + 1, 1}, algos{j + 1, 3});
        end
        p.series{end + 1} = struct('label', char(d.ids(i) + " " + tk + " " + names{j + 1}), 'x', {{i}}, 'y', {{hits}});
        p.text(p.X(a, (xa + xb) / 2), p.Y(a, hits) + s.pad * 0.9, sprintf('%d', hits), s.barnum, 'va', 'bottom');
    end
end
end

function fig5_key(p, xs, y)
p.key_bar(xs(1), y, 'GA', 'GA', 's');
p.key_bar(xs(2), y, 'NSGA', 'NSGA-II', 'd');
p.key_bar(xs(3), y, 'GALS', 'GA + local search', 'o');
end

function r = fig_Fig5(d, S, s, rawdir)
tks = ["t0125" "t0183"];
ylab = sprintf('Runs at the optimum (of %d)', d.seeds);
if strcmp(s.mode, 'paper')
    W = 190; H = 112;
    p = Page('Fig5_algorithms', W, H, s, S);
    g = grid(W, H, 13, 2, 11, 12.5, 0, 9, 2, 1);
    for i = 1:2
        a = algo_axes(d, p, g{i, 1}, tks(i), i == 2);
        p.panel(a, char('a' + i - 1), S.thick_text.(char(tks(i))));
        p.ylabel(a, ylab, 3.4);
        if i == 2, p.xlabel(a, 'Load case', 1.2); end
    end
    fig5_key(p, [13 38 72], H - 3.5);
    r = {p.save(rawdir)};
    return
end
r = {};
for tk = tks
    W = S.slide_W; H = S.slide_H;
    p = Page(char("Fig5_algorithms_" + tk), W, H, s, S);
    a = algo_axes(d, p, [28 22 W - 33 H - 46], tk, true);
    p.xlabel(a, 'Load case', 3);
    p.ylabel(a, ylab, 10);
    fig5_key(p, [28 85 185], H - 8);
    p.text(W - 5, H - 8, S.thick_text.(char(tk)), s.legend, 'ha', 'right');
    r{end + 1} = p.save(rawdir); %#ok<AGROW>
end
end

% ---------------------------------------------------------------------------------------------- FigS2, FigS3
function rep = conv_page(d, S, s, rawdir, tk, name, cases, first)
W = 190; H = 128;
p = Page(name, W, H, s, S);
g = grid(W, H, 13, 4.5, 11, 12.5, 7, 9, 2, 2);
allhits = [d.R.hit_evals];
x0 = axis_start(min(allhits));
xt = [30 100 300 1000 3000 d.budget]; yt = [0 25 50 75 100];
algos = {'GA', 'ga', '--', 'GA'; 'NSGA', 'nsga2', '-.', 'NSGA-II'; 'GALS', 'ga_ls', '-', 'GA + LS'};
axs = cell(1, 4);
for i = 1:4
    r0 = floor((i - 1) / 2) + 1; qc = mod(i - 1, 2) + 1;
    xl = {}; yl = {};
    if r0 == 2, xl = num_labels(xt); end
    if qc == 1, yl = num_labels(yt); end
    a = p.axes(g{r0, qc}, [x0 d.budget], [0 104], 'xlog', true, 'xticks', xt, 'yticks', yt, 'xlabels', xl, 'ylabels', yl);
    c = cases(i);
    q = row(d.T, c, tk);
    drawn = 0;
    for j = 1:3
        sel = arrayfun(@(u) strcmp(u.case, char(c)) && strcmp(u.tkey, char(tk)) && strcmp(u.method, algos{j, 2}), d.R);
        rr = d.R(sel);
        hits = [];
        for u = rr'
            h = reshape(u.history, [], 3);
            if h(end, 2) == q.n_opt && h(end, 3) >= q.margin_opt * (1 - 1e-9) && ~isempty(u.hit_evals)
                hits(end + 1) = u.hit_evals; %#ok<AGROW>
            end
        end
        if proven(q)
            [xx, yy] = ecdf_xy(hits, numel(rr), x0, d.budget);
            p.line(a, xx, yy, algos{j, 1}, 'ls', algos{j, 3}, 'label', sprintf('%s %s %s', c, tk, algos{j, 4}));
            drawn = drawn + numel(hits);
        end
    end
    if drawn == 0
        txt = 'no run reached the optimum';
        if ~proven(q), txt = 'no proven optimum'; end
        p.text(a.box(1) + a.box(3) / 2, a.box(2) + a.box(4) / 2, txt, s.legend);
    end
    p.panel(a, char('a' + first + i - 1), char(c + " " + q.name_en));
    axs{i} = a;
end
p.xlabel(axs{3}, 'Distinct designs evaluated', 1.2);
p.xlabel(axs{4}, 'Distinct designs evaluated', 1.2);
p.ylabel(axs{1}, 'Runs at the optimum (\%)', 3.4);
p.ylabel(axs{3}, 'Runs at the optimum (\%)', 3.4);
p.key_line(13, H - 3.5, 'GA', 'GA', 'ls', '--');
p.key_line(38, H - 3.5, 'NSGA', 'NSGA-II', 'ls', '-.');
p.key_line(72, H - 3.5, 'GALS', 'GA + local search', 'ls', '-');
rep = p.save(rawdir);
end

function r = fig_FigS2(d, S, s, rawdir)
r = {conv_page(d, S, s, rawdir, "t0125", 'FigS2_convergence_t0125_p1', d.ids(1:4), 0), ...
    conv_page(d, S, s, rawdir, "t0125", 'FigS2_convergence_t0125_p2', d.ids(5:8), 4)};
end

function r = fig_FigS3(d, S, s, rawdir)
r = {conv_page(d, S, s, rawdir, "t0183", 'FigS3_convergence_t0183_p1', d.ids(1:4), 0), ...
    conv_page(d, S, s, rawdir, "t0183", 'FigS3_convergence_t0183_p2', d.ids(5:8), 4)};
end

% ---------------------------------------------------------------------------------------------------- FigS4
function r = fig_FigS4(d, S, s, rawdir)
W = 190; H = 68;
p = Page('FigS4_best_so_far_C4', W, H, s, S);
g = grid(W, H, 13, 4.5, 11, 12.5, 7, 0, 1, 3);
gx = logspace(log10(20), log10(d.budget), 501);
c = 'C4'; tk = 't0125';
n_o = row(d.T, "C4", "t0125").n_opt;
algos = {'GA', 'ga', '--', 'GA', 'GA'; 'NSGA', 'nsga2', '-.', 'NSGA-II', 'NSGA-II'; ...
    'GALS', 'ga_ls', '-', 'GA + LS', 'GA + local search'};
curves = cell(3, 1); tops = zeros(1, 3);
for j = 1:3
    sel = arrayfun(@(u) strcmp(u.case, c) && strcmp(u.tkey, tk) && strcmp(u.method, algos{j, 2}), d.R);
    rr = d.R(sel);
    vals = nan(numel(rr), numel(gx));
    for i = 1:numel(rr)
        h = reshape(rr(i).history, [], 3);
        for q = 1:numel(gx)
            kk = find(h(:, 1) <= gx(q), 1, 'last');
            if ~isempty(kk), vals(i, q) = h(kk, 2); end
        end
    end
    keep = all(isfinite(vals), 1);
    v = vals(:, keep);
    curves{j} = struct('x', gx(keep), 'lo', prct(v, 25), 'med', prct(v, 50), 'hi', prct(v, 75));
    tops(j) = max(curves{j}.hi);
end
yt = n_o:1:(max(tops) + 0.5);
xt = [30 100 300 1000 3000 d.budget];
axs = cell(1, 3);
for j = 1:3
    yl = {}; if j == 1, yl = num_labels(yt); end
    a = p.axes(g{1, j}, [20 d.budget], [n_o - 0.8, max(tops) + 0.5], 'xlog', true, 'xticks', xt, 'yticks', yt, ...
        'xlabels', num_labels(xt), 'ylabels', yl);
    q = curves{j};
    p.hline(a, n_o, 'ls', ':');
    p.line(a, q.x, q.lo, algos{j, 1}, 'ls', '-', 'lw', s.thin, 'label', [algos{j, 4} ' q25']);
    p.line(a, q.x, q.hi, algos{j, 1}, 'ls', '-', 'lw', s.thin, 'label', [algos{j, 4} ' q75']);
    p.line(a, q.x, q.med, algos{j, 1}, 'ls', algos{j, 3}, 'label', [algos{j, 4} ' median']);
    p.panel(a, char('a' + j - 1), algos{j, 5});
    p.xlabel(a, 'Distinct designs evaluated', 1.2);
    axs{j} = a;
end
p.ylabel(axs{1}, 'Plies of the best design so far', 3.4);
y = H - 3.5;
p.key_line(13, y, 'exact', 'Median', 'ls', '-');
p.key_line(40, y, 'exact', '25th and 75th percentiles', 'ls', '-', 'lw', s.thin);
p.key_line(96, y, 'exact', 'Exact optimum', 'ls', ':', 'lw', s.ref_lw);
r = {p.save(rawdir)};
end

% ---------------------------------------------------------------------------------------------------- FigS5
function r = fig_FigS5(d, S, s, rawdir)
W = 190; H = 82;
p = Page('FigS5_ritz_before_after', W, H, s, S);
g = grid(W, H, 13, 2, 11, 12.5, 6, 0, 1, 2);
yt = [0 20 40 60];
top = d.nmax * 1.14;
tks = ["t0125" "t0183"];
n = numel(d.ids);
w = 0.38; gap = 0.015;
for i = 1:2
    tk = tks(i);
    yl = {}; if i == 1, yl = num_labels(yt); end
    a = p.axes(g{1, i}, [0.4 n + 0.6], [0 top], 'xticks', 1:n, 'yticks', yt, 'xlabels', cellstr(d.ids), 'ylabels', yl);
    for j = 1:n
        c = d.ids(j);
        items = {'qi', row(d.O, c, tk), j - w - gap, 's'; 'opt', row(d.T, c, tk), j + gap, 'o'};
        for q = 1:2
            role = items{q, 1}; rr = items{q, 2}; xa = items{q, 3}; xb = xa + w;
            if feasible(rr)
                p.bar(a, xa, xb, rr.n_opt, role, items{q, 4});
                p.text(p.X(a, (xa + xb) / 2), p.Y(a, rr.n_opt) + s.pad * 0.9, sprintf('%d', rr.n_opt), s.barnum, 'va', 'bottom');
            else
                p.hatch_bar(a, xa, xb, d.nmax, role);
                if strcmp(role, 'opt')
                    p.text(p.X(a, j), p.Y(a, d.nmax) + s.pad * 0.9, sprintf('${>}%d$', d.nmax), s.barnum, 'va', 'bottom');
                end
            end
        end
    end
    p.panel(a, char('a' + i - 1), S.thick_text.(char(tk)));
    p.xlabel(a, 'Load case', 1.2);
    if i == 1, p.ylabel(a, 'Optimised plies', 3.4); end
end
p.key_bar(13, H - 3.5, 'qi', 'Before: closed form, shear buckling not checked', 's');
p.key_bar(104, H - 3.5, 'opt', 'After: Rayleigh-Ritz', 'o');
r = {p.save(rawdir)};
end
