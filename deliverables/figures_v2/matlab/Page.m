classdef Page < handle
    %PAGE One figure: data axes at fixed positions in mm and one transparent overlay in mm that holds all text.
    %   Same layout calls as the Page class of python\style.py, so that both versions have the same geometry.

    properties
        name; W; H; s; S; k; fig; ov
        texts = {}; inside = {}; segs = zeros(0, 4); rects = zeros(0, 4); marks = zeros(0, 3); blocks = zeros(0, 4)
        series = {}; axes_list = {}
    end

    methods
        function p = Page(name, W, H, s, S)
            p.name = name; p.W = W; p.H = H; p.s = s; p.S = S; p.k = S.k;
            p.fig = figure('Units', 'centimeters', 'Position', [0.5 0.5 W * p.k / 10 H * p.k / 10], 'Color', 'w', ...
                'Visible', 'off', 'Renderer', 'painters', 'InvertHardcopy', 'off');
            p.ov = axes(p.fig, 'Units', 'normalized', 'Position', [0 0 1 1], 'Visible', 'off', 'XLim', [0 W], ...
                'YLim', [0 H], 'Color', 'none');
            hold(p.ov, 'on');
        end

        % -------------------------------------------------------------------------- axes and coordinates
        function a = axes(p, box, xlim, ylim, opt)
            arguments
                p; box; xlim; ylim
                opt.xlog = false; opt.ylog = false
                opt.xticks = []; opt.yticks = []; opt.xlabels = {}; opt.ylabels = {}
            end
            s = p.s;
            a = struct('box', box, 'xl', xlim, 'yl', ylim, 'xlog', opt.xlog, 'ylog', opt.ylog);
            a.h = axes(p.fig, 'Units', 'normalized', 'Position', box ./ [p.W p.H p.W p.H], 'Box', 'off', ...
                'TickDir', 'out', 'LineWidth', s.axes * p.k, 'XColor', 'k', 'YColor', 'k', 'Color', 'none', ...
                'XLim', xlim, 'YLim', ylim, 'XTick', sort(opt.xticks), 'YTick', sort(opt.yticks), 'XTickLabel', {}, ...
                'YTickLabel', {}, 'TickLength', [s.ticklen / max(box(3:4)) 0], 'XMinorTick', 'off', 'YMinorTick', 'off', ...
                'Layer', 'top');
            if opt.xlog, a.h.XScale = 'log'; end
            if opt.ylog, a.h.YScale = 'log'; end
            a.h.XLim = xlim; a.h.YLim = ylim;
            a.h.XTick = sort(opt.xticks); a.h.YTick = sort(opt.yticks);
            a.h.XTickLabel = {}; a.h.YTickLabel = {};
            a.h.XAxis.MinorTick = 'off'; a.h.YAxis.MinorTick = 'off';
            hold(a.h, 'on');
            p.segs(end + 1, :) = [box(1) box(2) box(1) + box(3) box(2)];
            p.segs(end + 1, :) = [box(1) box(2) box(1) box(2) + box(4)];
            for i = 1:numel(opt.xlabels)
                p.text(p.X(a, opt.xticks(i)), box(2) - s.ticklen - s.pad, opt.xlabels{i}, s.tick, 'va', 'top');
            end
            for i = 1:numel(opt.ylabels)
                p.text(box(1) - s.ticklen - s.pad, p.Y(a, opt.yticks(i)), opt.ylabels{i}, s.tick, 'ha', 'right');
            end
            p.axes_list{end + 1} = a;
            uistack(p.ov, 'top');
        end

        function x = X(~, a, v)
            if a.xlog
                f = (log10(v) - log10(a.xl(1))) ./ (log10(a.xl(2)) - log10(a.xl(1)));
            else
                f = (v - a.xl(1)) ./ (a.xl(2) - a.xl(1));
            end
            x = a.box(1) + f .* a.box(3);
        end

        function y = Y(~, a, v)
            if a.ylog
                f = (log10(v) - log10(a.yl(1))) ./ (log10(a.yl(2)) - log10(a.yl(1)));
            else
                f = (v - a.yl(1)) ./ (a.yl(2) - a.yl(1));
            end
            y = a.box(2) + f .* a.box(4);
        end

        % ------------------------------------------------------------------------------------------ text
        function t = text(p, x, y, str, size, opt)
            arguments
                p; x; y; str; size
                opt.ha = 'center'; opt.va = 'middle'; opt.rot = 0; opt.color = '#000000'; opt.inside = []
            end
            % every label is anchored on its baseline, which both versions place in the same way
            shift = struct('middle', 0.5, 'top', 1, 'bottom', 0, 'baseline', 0);
            y = y - shift.(opt.va) * 0.68 * size * 25.4 / 72;
            t = text(p.ov, x, y, str, 'FontSize', size * p.k, 'HorizontalAlignment', opt.ha, ...
                'VerticalAlignment', 'baseline', 'Rotation', opt.rot, 'Color', opt.color, 'Interpreter', 'latex', 'Clipping', 'off');
            p.texts{end + 1} = t;
            p.inside{end + 1} = opt.inside;
        end

        function xlabel(p, a, str, y)
            p.text(a.box(1) + a.box(3) / 2, y, str, p.s.label, 'va', 'bottom');
        end

        function ylabel(p, a, str, x)
            p.text(x + 0.34 * p.s.label * 25.4 / 72, a.box(2) + a.box(4) / 2, str, p.s.label, 'rot', 90, 'va', 'baseline');
        end

        function panel(p, a, letter, name)
            s = p.s;
            yt = a.box(2) + a.box(4) + s.pad * 1.3;
            p.text(a.box(1), yt, sprintf('\\textbf{(%s)}', letter), s.panel, 'ha', 'left', 'va', 'baseline');
            if nargin > 3 && strlength(name) > 0
                p.text(a.box(1) + s.panel * 25.4 / 72 * 2.1, yt, name, s.name, 'ha', 'left', 'va', 'baseline');
            end
        end

        % ------------------------------------------------------------------------------------- data marks
        function line(p, a, x, y, role, opt)
            arguments
                p; a; x; y; role
                opt.ls = '-'; opt.lw = []; opt.marker = ''; opt.ms = []; opt.mfc = []; opt.mew = []
                opt.every = []; opt.label = ''; opt.top = false
            end
            s = p.s;
            c = p.S.role.(role);
            x = x(:)'; y = y(:)';
            lw = opt.lw; if isempty(lw), lw = s.lw; end
            ms = opt.ms; if isempty(ms), ms = s.ms; end
            mew = opt.mew; if isempty(mew), mew = s.mew; end
            box = [a.box(1) a.box(2) a.box(1) + a.box(3) a.box(2) + a.box(4)];
            xy = [p.X(a, x)' p.Y(a, y)'];
            if ~strcmp(opt.ls, 'none')
                seg = clip_to_box(xy, box);
                p.stroke(seg, opt.ls, lw, c);
                p.segs = [p.segs; seg];
            end
            if ~isempty(opt.marker)
                idx = 1:numel(x);
                if ~isempty(opt.every), idx = (opt.every(1) + 1):opt.every(2):numel(x); end
                mfc = opt.mfc; if isempty(mfc), mfc = c; end
                inside = xy(idx, 1) >= box(1) & xy(idx, 1) <= box(3) & xy(idx, 2) >= box(2) & xy(idx, 2) <= box(4);
                q = xy(idx(inside), :);
                p.mark(opt.marker, q(:, 1), q(:, 2), ms, mfc, c, mew);
                p.marks = [p.marks; q repmat(ms * 25.4 / 72 / 2, size(q, 1), 1)];
            end
            lab = opt.label; if isempty(lab), lab = role; end
            p.series{end + 1} = struct('label', lab, 'x', {num2cell(x)}, 'y', {num2cell(y)});
        end

        function hline(p, a, y, opt)
            arguments
                p; a; y
                opt.role = 'exact'; opt.ls = '--'; opt.lw = []
            end
            lw = opt.lw; if isempty(lw), lw = p.s.ref_lw; end
            ym = p.Y(a, y);
            seg = [a.box(1) ym a.box(1) + a.box(3) ym];
            p.stroke(seg, opt.ls, lw, p.S.role.(opt.role));
            p.segs(end + 1, :) = seg;
        end

        function bar(p, a, x0, x1, h, role, mark)
            c = p.S.role.(role);
            patch(a.h, 'XData', [x0 x1 x1 x0], 'YData', [0 0 h h], 'FaceColor', c, 'EdgeColor', 'none', 'FaceAlpha', 1);
            xa = p.X(a, x0); xb = p.X(a, x1); ya = p.Y(a, 0); yb = p.Y(a, h);
            p.rects(end + 1, :) = [xa ya xb yb];
            p.series{end + 1} = struct('label', ['bar ' role], 'x', {{x0, x1}}, 'y', {{0, h}});
            s = p.s;
            mm = s.ms * 25.4 / 72;
            if nargin > 6 && ~isempty(mark) && (yb - ya) > 3 * mm
                p.mark(mark, (xa + xb) / 2, ya + 1.5 * mm, s.ms, p.S.WHITE, p.S.WHITE, 0);
            end
        end

        function hatch_bar(p, a, x0, x1, h, role)
            s = p.s;
            c = p.S.role.(role);
            xa = p.X(a, x0); xb = p.X(a, x1); ya = p.Y(a, 0); yb = p.Y(a, h);
            p.hatch_lines(xa, ya, xb, yb, c);
            rectangle(p.ov, 'Position', [xa ya xb - xa yb - ya], 'FaceColor', 'none', 'EdgeColor', c, 'LineWidth', s.border * p.k);
            p.rects(end + 1, :) = [xa ya xb yb];
            p.series{end + 1} = struct('label', ['open bar ' role], 'x', {{x0, x1}}, 'y', {{0, h}});
        end

        function hatch_lines(p, xa, ya, xb, yb, c)
            s = p.s;
            step = 1.5; if strcmp(s.mode, 'slide'), step = 3.0; end
            q = xa - (yb - ya);
            while q < xb
                seg = clip_to_box([q ya; q + (yb - ya) yb], [xa ya xb yb]);
                for i = 1:size(seg, 1)
                    plot(p.ov, seg(i, [1 3]), seg(i, [2 4]), 'Color', c, 'LineWidth', s.thin * 0.75 * p.k, 'LineStyle', '-');
                end
                q = q + step;
            end
        end

        function stroke(p, seg, ls, lw, c)
            % Polyline on the overlay; segments in mm, dash patterns (in line widths) as in matplotlib
            pats = struct('dash', [3.7 1.6], 'dashdot', [6.4 1.6 1 1.6], 'dot', [1 1.65]);
            X = []; Y = [];
            if strcmp(ls, '-')
                for i = 1:size(seg, 1)
                    if i == 1 || norm(seg(i, 1:2) - seg(i - 1, 3:4)) > 1e-9
                        X = [X NaN seg(i, 1)]; Y = [Y NaN seg(i, 2)]; %#ok<AGROW>
                    end
                    X(end + 1) = seg(i, 3); Y(end + 1) = seg(i, 4); %#ok<AGROW>
                end
            else
                switch ls
                    case '--', pat = pats.dash;
                    case '-.', pat = pats.dashdot;
                    otherwise, pat = pats.dot;
                end
                pat = pat * lw * 25.4 / 72;
                i = 1; left = pat(1);
                for j = 1:size(seg, 1)
                    L = hypot(seg(j, 3) - seg(j, 1), seg(j, 4) - seg(j, 2));
                    if L == 0, continue; end
                    u = (seg(j, 3:4) - seg(j, 1:2)) / L;
                    t0 = 0;
                    while t0 < L
                        d = min(left, L - t0);
                        if mod(i, 2) == 1
                            q0 = seg(j, 1:2) + t0 * u; q1 = q0 + d * u;
                            X = [X q0(1) q1(1) NaN]; Y = [Y q0(2) q1(2) NaN]; %#ok<AGROW>
                        end
                        t0 = t0 + d; left = left - d;
                        if left <= 1e-9
                            i = mod(i, numel(pat)) + 1; left = pat(i);
                        end
                    end
                end
            end
            plot(p.ov, X, Y, 'LineStyle', '-', 'LineWidth', lw * p.k, 'Color', c, 'LineJoin', 'miter');
        end

        function mark(p, kind, x, y, ms, fc, ec, mew)
            % Markers on the overlay, with the geometry of the Python markers
            m = ms * 25.4 / 72;
            if strcmp(fc, 'none'), ff = 'none'; else, ff = fc; end
            if strcmp(kind, 'o')
                if isempty(x), return; end
                w = max(mew, 0.01);
                plot(p.ov, x, y, 'LineStyle', 'none', 'Color', ec, 'Marker', 'o', 'MarkerSize', ms * p.k, ...
                    'MarkerFaceColor', ff, 'MarkerEdgeColor', ec, 'LineWidth', w * p.k);
                return
            end
            switch kind
                case 's', vx = [-1 1 1 -1] * m / 2; vy = [-1 -1 1 1] * m / 2;
                case 'd', vx = [0 1 0 -1] * m * 0.7071; vy = [-1 0 1 0] * m * 0.7071;
                case '^', vx = [-1 1 0] * m / 2; vy = [-1 -1 1] * m / 2;
            end
            for i = 1:numel(x)
                if mew > 0
                    patch(p.ov, 'XData', x(i) + vx, 'YData', y(i) + vy, 'FaceColor', ff, 'EdgeColor', ec, 'LineWidth', mew * p.k);
                else
                    patch(p.ov, 'XData', x(i) + vx, 'YData', y(i) + vy, 'FaceColor', ff, 'EdgeColor', 'none');
                end
            end
        end

        % -------------------------------------------------------------------- legend strip, blocks, arrows
        function key_line(p, x, y, role, label, opt)
            arguments
                p; x; y; role; label
                opt.ls = '-'; opt.marker = ''; opt.mfc = []; opt.ms = []; opt.mew = []; opt.lw = []
            end
            s = p.s;
            c = p.S.role.(role);
            drawn = ~strcmp(opt.ls, 'none');
            wide = s.sample; if ~drawn, wide = s.sample * 0.45; end
            lw = opt.lw; if isempty(lw), lw = s.lw; end
            ms = opt.ms; if isempty(ms), ms = s.ms; end
            mew = opt.mew; if isempty(mew), mew = s.mew; end
            if drawn
                p.stroke([x y x + wide y], opt.ls, lw, c);
            end
            if ~isempty(opt.marker)
                mfc = opt.mfc; if isempty(mfc), mfc = c; end
                p.mark(opt.marker, x + wide / 2, y, ms, mfc, c, mew);
            end
            p.text(x + wide + 1.2 * s.pad, y, label, s.legend, 'ha', 'left');
        end

        function key_bar(p, x, y, role, label, mark, hatch)
            s = p.s;
            c = p.S.role.(role);
            w = s.sample * 0.8;
            h = s.legend * 25.4 / 72 * 0.95;
            if nargin > 6 && hatch
                p.hatch_lines(x, y - h / 2, x + w, y + h / 2, c);
                rectangle(p.ov, 'Position', [x y - h / 2 w h], 'FaceColor', 'none', 'EdgeColor', c, 'LineWidth', s.border * p.k);
            else
                patch(p.ov, 'XData', [x x + w x + w x], 'YData', [y - h / 2 y - h / 2 y + h / 2 y + h / 2], 'FaceColor', c, 'EdgeColor', 'none');
                if ~isempty(mark)
                    p.mark(mark, x + w / 2, y, s.ms * 0.9, p.S.WHITE, p.S.WHITE, 0);
                end
            end
            p.text(x + w + 1.2 * s.pad, y, label, s.legend, 'ha', 'left');
        end

        function block(p, x, y, w, h, lines, kind)
            s = p.s;
            fc = p.S.WHITE;
            if isfield(p.S.block, kind), fc = p.S.block.(kind); end
            r = s.corner;
            rectangle(p.ov, 'Position', [x y w h], 'Curvature', min(1, [2 * r / w 2 * r / h]), 'FaceColor', fc, ...
                'EdgeColor', 'k', 'LineWidth', s.border * p.k);
            box = [x y x + w y + h];
            p.blocks(end + 1, :) = box;
            color = p.S.BLACK;
            if any(strcmp(kind, {'llm', 'check'})), color = p.S.WHITE; end
            lead = s.block * 25.4 / 72 * 1.22;
            y0 = y + h / 2 + (numel(lines) - 1) * lead / 2;
            for i = 1:numel(lines)
                p.text(x + w / 2, y0 - (i - 1) * lead, lines{i}, s.block, 'color', color, 'inside', box);
            end
        end

        function arrow(p, a, b)
            s = p.s;
            L = 1.7; Wd = 0.7;
            if strcmp(s.mode, 'slide'), L = 3.4; Wd = 1.4; end
            d = (b - a) / hypot(b(1) - a(1), b(2) - a(2));
            n = [-d(2) d(1)];
            base = b - L * d;
            plot(p.ov, [a(1) base(1)], [a(2) base(2)], 'Color', 'k', 'LineWidth', s.border * p.k, 'LineStyle', '-');
            patch(p.ov, 'XData', [b(1) base(1) + Wd * n(1) base(1) - Wd * n(1)], 'YData', [b(2) base(2) + Wd * n(2) base(2) - Wd * n(2)], ...
                'FaceColor', 'k', 'EdgeColor', 'none');
            p.segs(end + 1, :) = [a b];
        end

        function wire(p, a, b)
            plot(p.ov, [a(1) b(1)], [a(2) b(2)], 'Color', 'k', 'LineWidth', p.s.border * p.k, 'LineStyle', '-');
            p.segs(end + 1, :) = [a b];
        end

        % --------------------------------------------------------------------------------------- checks
        function boxes = text_boxes(p)
            boxes = zeros(numel(p.texts), 4);
            for i = 1:numel(p.texts)
                e = p.texts{i}.Extent;
                boxes(i, :) = [e(1) e(2) e(1) + e(3) e(2) + e(4)];
            end
        end

        function bad = collisions(p)
            b = p.text_boxes();
            % Extent includes the line box of the interpreter: compare the glyph area, as get_window_extent does
            pad = 0.10 * (b(:, 4) - b(:, 2));
            b(:, 2) = b(:, 2) + pad; b(:, 4) = b(:, 4) - pad;
            bad = {};
            for i = 1:size(b, 1)
                ti = string(p.texts{i}.String);
                ti = ti(1);
                if b(i, 1) < 0 || b(i, 2) < 0 || b(i, 3) > p.W || b(i, 4) > p.H
                    bad{end + 1} = "outside the page: " + ti; %#ok<AGROW>
                end
                for j = i + 1:size(b, 1)
                    if overlaps(b(i, :), b(j, :))
                        bad{end + 1} = "text/text: " + ti + " | " + string(p.texts{j}.String(1)); %#ok<AGROW>
                    end
                end
                if ~isempty(p.inside{i})
                    q = p.inside{i};
                    if b(i, 1) < q(1) || b(i, 2) < q(2) || b(i, 3) > q(3) || b(i, 4) > q(4)
                        bad{end + 1} = "text leaves its block: " + ti; %#ok<AGROW>
                    end
                end
                for j = 1:size(p.rects, 1)
                    if overlaps(b(i, :), p.rects(j, :))
                        bad{end + 1} = "text/column: " + ti; %#ok<AGROW>
                    end
                end
                if isempty(p.inside{i})
                    for j = 1:size(p.blocks, 1)
                        if overlaps(b(i, :), p.blocks(j, :))
                            bad{end + 1} = "text/block: " + ti; %#ok<AGROW>
                        end
                    end
                end
                for j = 1:size(p.segs, 1)
                    if seg_hits_box(p.segs(j, :), b(i, :))
                        bad{end + 1} = "text/line: " + ti; %#ok<AGROW>
                        break
                    end
                end
                m = p.marks;
                if ~isempty(m) && any(b(i, 1) - m(:, 3) < m(:, 1) & m(:, 1) < b(i, 3) + m(:, 3) & ...
                        b(i, 2) - m(:, 3) < m(:, 2) & m(:, 2) < b(i, 4) + m(:, 3))
                    bad{end + 1} = "text/marker: " + ti; %#ok<AGROW>
                end
            end
            bad = cellstr(unique(string(bad)));
            if isequal(bad, {''}), bad = {}; end
        end

        function bad = colour_scan(p)
            bad = {};
            ok = p.S.palette;
            all_objs = findall(p.fig);
            for i = 1:numel(all_objs)
                h = all_objs(i);
                switch h.Type
                    case 'line'
                        bad = add_colour(bad, ok, h.Color, 'line');
                        if ~strcmp(h.Marker, 'none')
                            bad = add_colour(bad, ok, h.MarkerFaceColor, 'marker face');
                            bad = add_colour(bad, ok, h.MarkerEdgeColor, 'marker edge');
                        end
                    case 'patch'
                        bad = add_colour(bad, ok, h.FaceColor, 'patch face');
                        bad = add_colour(bad, ok, h.EdgeColor, 'patch edge');
                        if isnumeric(h.FaceAlpha) && h.FaceAlpha < 1, bad{end + 1} = 'alpha on patch'; end %#ok<AGROW>
                    case 'rectangle'
                        bad = add_colour(bad, ok, h.FaceColor, 'block face');
                        bad = add_colour(bad, ok, h.EdgeColor, 'block edge');
                    case 'text'
                        if ~isempty(h.String)
                            hexc = lower(rgb2hexs(h.Color));
                            if ~strcmp(hexc, '#000000') && ~strcmp(hexc, '#ffffff')
                                bad{end + 1} = ['text colour ' hexc]; %#ok<AGROW>
                            end
                        end
                end
            end
            for i = 1:numel(p.texts)
                if isempty(p.inside{i}) && ~strcmp(lower(rgb2hexs(p.texts{i}.Color)), '#000000')
                    bad{end + 1} = 'white text outside a block'; %#ok<AGROW>
                end
            end
            bad = unique(bad);
        end

        % ---------------------------------------------------------------------------------------- output
        function rep = save(p, rawdir)
            drawnow;
            rep = struct('name', p.name, 'mode', p.s.mode);
            rep.collisions = p.collisions();
            rep.colours = p.colour_scan();
            sizes = cellfun(@(t) t.FontSize / p.k, p.texts);
            rep.fonts = struct('min_size', min(sizes), 'bad', {{}});
            rep.n_text = numel(p.texts);
            rep.titles = false;
            rep.series = p.series;
            rep.text = cellfun(@(t) char(strjoin(string(t.String), ' ')), p.texts, 'UniformOutput', false);
            nm = p.name;
            if strcmp(p.s.mode, 'slide'), nm = [nm '_slide']; end
            exportgraphics(p.fig, fullfile(rawdir, [nm '.pdf']), 'ContentType', 'vector', 'BackgroundColor', 'white', ...
                'Padding', 'figure');
            close(p.fig);
        end
    end
end

function tf = overlaps(a, b)
tol = 0.05;
tf = a(1) < b(3) - tol && b(1) < a(3) - tol && a(2) < b(4) - tol && b(2) < a(4) - tol;
end

function tf = seg_hits_box(seg, box)
t0 = 0; t1 = 1;
dx = seg(3) - seg(1); dy = seg(4) - seg(2);
ds = [dx dy]; as = seg(1:2); los = box(1:2); his = box(3:4);
tf = false;
for i = 1:2
    d = ds(i); a = as(i); lo = los(i); hi = his(i);
    if abs(d) < 1e-12
        if a <= lo || a >= hi, return; end
        continue
    end
    u = (lo - a) / d; v = (hi - a) / d;
    if u > v, tmp = u; u = v; v = tmp; end
    t0 = max(t0, u); t1 = min(t1, v);
    if t0 >= t1, return; end
end
tf = true;
end

function bad = add_colour(bad, ok, c, what)
if ischar(c) || isstring(c)
    if any(strcmp(c, {'none', 'flat', 'interp'})), return; end
    if strcmp(c, 'auto'), return; end
end
hexc = lower(rgb2hexs(c));
if ~any(strcmp(hexc, ok))
    bad{end + 1} = ['colour ' hexc ' on ' what];
end
end

function h = rgb2hexs(c)
if ischar(c) || isstring(c)
    h = char(c);
    if ~startsWith(h, '#')
        h = rgb2hexs(validatecolor(h));
    end
    return
end
h = sprintf('#%02X%02X%02X', round(c * 255));
end
