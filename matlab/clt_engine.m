function result = clt_engine(problem, material)
% CLT_ENGINE  Classical Laminate Theory analysis of a composite laminate.
%   problem.plies(k).angle      ply angle in degrees
%   problem.plies(k).thickness  ply thickness (same length unit as z-output)
%   problem.loads.Nx/Ny/Nxy     in-plane force resultants (force / length)
%   problem.loads.Mx/My/Mxy     moment resultants (force*length / length), default 0
%   material.E1/E2/G12/nu12     elastic properties (consistent unit with loads)
%   material.Xt/Xc/Yt/Yc/S      strength values, same stress unit as Q (for failure index)
%
%   result.ABD            6x6 laminate stiffness matrix
%   result.eps0           [ex0 ey0 gxy0] mid-plane strain
%   result.kappa          [kx ky kxy] mid-plane curvature
%   result.ply_angle      1xN list of ply angles (for reference)
%   result.ply_stress     Nx3 matrix, each row = [sigma1 sigma2 tau12] of that ply (material axes)
%   result.ply_strain     Nx3 matrix, each row = [eps1 eps2 gamma12] of that ply (material axes)
%   result.failure_index  Nx1 vector, Max-Stress failure index of each ply (>=1 means failed)
%   result.max_failure_index  scalar, worst ply (the number to check against 1)
%   result.critical_ply       index of the ply with the worst failure_index

    n = numel(problem.plies);
    angles = zeros(1, n);
    thick  = zeros(1, n);
    for k = 1:n
        % problem.plies arrives from Python as a MATLAB cell array of structs
        % (a Python list-of-dicts becomes a cell array, not a struct array),
        % so each ply must be unwrapped with {} before .field is valid.
        ply_k = problem.plies{k};
        angles(k) = ply_k.angle;
        thick(k)  = ply_k.thickness;
    end

    % ---- single-ply reduced stiffness matrix Q (material 1-2 axes) ----
    E1 = material.E1; E2 = material.E2; G12 = material.G12; nu12 = material.nu12;
    nu21 = nu12 * E2 / E1;
    denom = 1 - nu12 * nu21;
    Q = [E1/denom,        nu12*E2/denom, 0;
         nu12*E2/denom,   E2/denom,      0;
         0,                0,             G12];

    % ---- z-coordinates of ply boundaries, measured from the mid-plane ----
    total_t = sum(thick);
    z = zeros(1, n+1);
    z(1) = -total_t/2;
    for k = 1:n
        z(k+1) = z(k) + thick(k);
    end

    % ---- assemble A, B, D by summing each ply's rotated stiffness Qbar ----
    A = zeros(3,3); B = zeros(3,3); D = zeros(3,3);
    Qbar_list = cell(1, n);
    for k = 1:n
        Qbar_list{k} = rotate_Q(Q, angles(k));
        A = A + Qbar_list{k} * (z(k+1)   - z(k)  );
        B = B + Qbar_list{k} * (z(k+1)^2 - z(k)^2) / 2;
        D = D + Qbar_list{k} * (z(k+1)^3 - z(k)^3) / 3;
    end
    ABD = [A, B; B, D];

    % ---- apply loads, solve for mid-plane strain and curvature ----
    N = [problem.loads.Nx; problem.loads.Ny; problem.loads.Nxy];
    if isfield(problem.loads, 'Mx'), Mx = problem.loads.Mx; else, Mx = 0; end
    if isfield(problem.loads, 'My'), My = problem.loads.My; else, My = 0; end
    if isfield(problem.loads, 'Mxy'), Mxy = problem.loads.Mxy; else, Mxy = 0; end
    M = [Mx; My; Mxy];

    eps_kappa = ABD \ [N; M];
    eps0  = eps_kappa(1:3)';
    kappa = eps_kappa(4:6)';

    % ---- per-ply strain/stress in material axes, and Max-Stress failure index ----
    ply_stress = zeros(n, 3);
    ply_strain = zeros(n, 3);
    failure_index = zeros(n, 1);
    for k = 1:n
        zmid = (z(k) + z(k+1)) / 2;
        eps_xy = eps0 + zmid * kappa;                 % strain in laminate axes, at ply mid-height
        eps_12 = rotate_strain(eps_xy, angles(k));     % strain in material (1-2) axes
        sigma_12 = (Q * eps_12')';                     % stress in material axes
        ply_strain(k, :) = eps_12;
        ply_stress(k, :) = sigma_12;
        failure_index(k) = max_stress_index(sigma_12, material);
    end

    [max_fi, critical_k] = max(failure_index);

    result.ABD = ABD;
    result.eps0 = eps0;
    result.kappa = kappa;
    result.ply_angle = angles;
    result.ply_stress = ply_stress;
    result.ply_strain = ply_strain;
    result.failure_index = failure_index;
    result.max_failure_index = max_fi;
    result.critical_ply = critical_k;
end


function Qbar = rotate_Q(Q, theta_deg)
% Transform the reduced stiffness matrix Q (material axes) to the
% laminate x-y axes for a ply oriented at theta_deg.
    m = cosd(theta_deg); n = sind(theta_deg);
    Q11 = Q(1,1); Q12 = Q(1,2); Q22 = Q(2,2); Q66 = Q(3,3);

    Qbar11 = Q11*m^4 + 2*(Q12+2*Q66)*m^2*n^2 + Q22*n^4;
    Qbar22 = Q11*n^4 + 2*(Q12+2*Q66)*m^2*n^2 + Q22*m^4;
    Qbar12 = (Q11+Q22-4*Q66)*m^2*n^2 + Q12*(m^4+n^4);
    Qbar66 = (Q11+Q22-2*Q12-2*Q66)*m^2*n^2 + Q66*(m^4+n^4);
    Qbar16 = (Q11-Q12-2*Q66)*m^3*n - (Q22-Q12-2*Q66)*m*n^3;
    Qbar26 = (Q11-Q12-2*Q66)*m*n^3 - (Q22-Q12-2*Q66)*m^3*n;

    Qbar = [Qbar11, Qbar12, Qbar16;
            Qbar12, Qbar22, Qbar26;
            Qbar16, Qbar26, Qbar66];
end


function eps_12 = rotate_strain(eps_xy, theta_deg)
% Transform engineering strain [ex, ey, gamma_xy] from laminate axes
% to material (1-2) axes for a ply oriented at theta_deg.
    m = cosd(theta_deg); n = sind(theta_deg);
    ex = eps_xy(1); ey = eps_xy(2); gxy = eps_xy(3);
    exy = gxy / 2;  % tensor shear strain

    e1  = ex*m^2 + ey*n^2 + 2*exy*m*n;
    e2  = ex*n^2 + ey*m^2 - 2*exy*m*n;
    g12 = 2*(-ex*m*n + ey*m*n + exy*(m^2-n^2));

    eps_12 = [e1, e2, g12];
end


function fi = max_stress_index(sigma_12, material)
% Max Stress failure Criterion for one ply. sigma_12 = [sigma1 sigma2 tau12].
% Returns the worst of the 3 ratios; >= 1 means that ply has failed.
    s1 = sigma_12(1); s2 = sigma_12(2); t12 = sigma_12(3);

    if s1 >= 0, r1 = s1 / material.Xt; else, r1 = -s1 / material.Xc; end
    if s2 >= 0, r2 = s2 / material.Yt; else, r2 = -s2 / material.Yc; end
    r6 = abs(t12) / material.S;

    fi = max([r1, r2, r6]);
end