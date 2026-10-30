function S = style_setup()
%STYLE_SETUP Shared style of the MATLAB figures: same values as python\style.py.
%   To change journal, edit this file only. Target: Elsevier, Composite Structures.
%   Everything is drawn 1.5 times larger and the PDF is scaled back by postprocess.py: MATLAB rounds LaTeX font sizes
%   down to whole pixels, and 1.5 times 7, 8, 9, 10 pt fall exactly on whole pixels.

set(groot, 'defaultTextInterpreter', 'latex', 'defaultAxesTickLabelInterpreter', 'latex', ...
    'defaultLegendInterpreter', 'latex');

S.k = 1.5;
S.slide_W = 338.67;
S.slide_H = 190.5;

S.BLACK = '#000000';  S.COBALT = '#0047AB';  S.ORANGE = '#D55E00';
S.GREEN = '#009E73';  S.PURPLE = '#6A1B9A';  S.MAGENTA = '#C2185B';  S.WHITE = '#FFFFFF';
S.palette = lower({S.BLACK, S.COBALT, S.ORANGE, S.GREEN, S.PURPLE, S.MAGENTA, S.WHITE});

r = struct();
r.qi = S.BLACK;   r.opt = S.COBALT;  r.GA = S.COBALT;  r.NSGA = S.ORANGE;  r.GALS = S.GREEN;
r.t0125 = S.ORANGE;  r.t0183 = S.PURPLE;  r.seed = S.MAGENTA;  r.exact = S.BLACK;
r.LHA = S.COBALT;  r.LHB = S.ORANGE;  r.LHC = S.GREEN;  r.LHD = S.MAGENTA;
S.role = r;

S.block = struct('llm', S.COBALT, 'data', S.GREEN, 'comp', S.ORANGE, 'check', S.PURPLE);
S.block_name = struct('llm', 'LLM', 'data', 'Data and ML', 'comp', 'Computation', 'check', 'Check');

S.thick_text = struct('t0125', '$t = 0.125\,\mathrm{mm}$', 't0183', '$t = 0.183\,\mathrm{mm}$');
S.thick_mark = struct('t0125', 'o', 't0183', 's');

S.paper = struct('mode', 'paper', 'label', 9, 'tick', 8, 'legend', 8, 'barnum', 7, 'panel', 10, 'name', 9, 'block', 8, ...
    'lw', 1.5, 'thin', 0.8, 'axes', 0.7, 'ticklen', 1.2, 'pad', 0.9, 'ms', 4.0, 'ms_small', 2.6, 'mew', 0.5, ...
    'sample', 7.0, 'border', 0.8, 'ref', 9, 'ref_lw', 1.3, 'corner', 1.2);
S.slide = struct('mode', 'slide', 'label', 20, 'tick', 18, 'legend', 18, 'barnum', 18, 'panel', 20, 'name', 18, 'block', 18, ...
    'lw', 3.0, 'thin', 1.6, 'axes', 1.4, 'ticklen', 2.4, 'pad', 1.8, 'ms', 9.0, 'ms_small', 6.0, 'mew', 1.0, ...
    'sample', 14.0, 'border', 1.6, 'ref', 18, 'ref_lw', 2.6, 'corner', 2.4);
end
