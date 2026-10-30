function out = clip_to_box(xy, box)
%CLIP_TO_BOX Keeps the parts of a polyline (N x 2) inside box [x0 y0 x1 y1], as rows [x0 y0 x1 y1].
out = zeros(0, 4);
for i = 1:size(xy, 1) - 1
    p = xy(i, :); q = xy(i + 1, :);
    if any(~isfinite([p q])), continue; end
    t0 = 0; t1 = 1; keep = true;
    d = q - p;
    for j = 1:2
        lo = box(j); hi = box(j + 2);
        if abs(d(j)) < 1e-12
            keep = keep && p(j) >= lo && p(j) <= hi;
            continue
        end
        u = (lo - p(j)) / d(j); v = (hi - p(j)) / d(j);
        if u > v, tmp = u; u = v; v = tmp; end
        t0 = max(t0, u); t1 = min(t1, v);
    end
    if keep && t0 <= t1
        out(end + 1, :) = [p + t0 * d, p + t1 * d]; %#ok<AGROW>
    end
end
end
