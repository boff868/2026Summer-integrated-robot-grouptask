# MIT VNAV Lab 3 — Deliverable 2

## A. Reverse the spin directions of rotors 3 and 4

Let the signed squared rotor speeds be (u_i=\omega_i|\omega_i|), and let (l=d/\sqrt{2}), where (d=\|\rho_i\|_2). From the simulator's top-view convention,

\[
\rho_1=(l,l,0),\quad \rho_2=(-l,l,0),\quad
\rho_3=(-l,-l,0),\quad \rho_4=(l,-l,0).
\]

With upward thrust (c_f u_i\,e_3) and the drag-torque signs shown in the handout, the nominal wrench map is

\[
\begin{bmatrix} f \\ \tau_x \\ \tau_y \\ \tau_z \end{bmatrix}
=F_a\begin{bmatrix}u_1\\u_2\\u_3\\u_4\end{bmatrix},\qquad
F_a=\begin{bmatrix}
c_f&c_f&c_f&c_f\\
lc_f&lc_f&-lc_f&-lc_f\\
-lc_f&lc_f&lc_f&-lc_f\\
c_d&-c_d&c_d&-c_d
\end{bmatrix}.
\]

Its determinant is \(\det(F_a)=-16l^2c_f^3c_d\), so it has rank four for nonzero \(l,c_f,c_d\). Reversing rotors 3 and 4 does not change their lift or locations, but flips their yaw-drag signs:

\[
F_b=\begin{bmatrix}
c_f&c_f&c_f&c_f\\
lc_f&lc_f&-lc_f&-lc_f\\
-lc_f&lc_f&lc_f&-lc_f\\
c_d&-c_d&-c_d&c_d
\end{bmatrix}.
\]

The last row is \(-c_d/(lc_f)\) times the pitch row. Thus \(\operatorname{rank}(F_b)=3\): pitch and yaw torques cannot be commanded independently. The modified vehicle cannot produce an arbitrary thrust/roll/pitch/yaw wrench, so it cannot track a general trajectory that specifies position and yaw independently.

## B. Compensate body drag

For body-frame velocity \(v^b=R^Tv\), define

\[
D=\operatorname{diag}(0.1,0.1,0.2),\qquad
F_d^b=-D\bigl(v^b\odot|v^b|\bigr),
\]

where absolute value and multiplication are componentwise. The world-frame drag is \(RF_d^b\). Under the ROS-up convention, the translational dynamics are

\[
m\dot v=Rf e_3-mg e_3+RF_d^b.
\]

For errors \(e_x=x-x_d\) and \(e_v=v-v_d\), first compute the nominal desired force

\[
F_{des}^{(0)}=-K_xe_x-K_ve_v+mg e_3+ma_d.
\]

Then cancel the predicted drag explicitly:

\[
F_{des}=F_{des}^{(0)}-RF_d^b.
\]

Because \(F_d^b\) opposes the body-frame velocity, subtracting it adds the force needed to offset drag. The controller recomputes this compensation from odometry at every control step before forming the desired attitude and thrust.

**References:** MIT VNAV Lab 3 exercise and Lecture 6, “Quadrotor Dynamics”; T. Lee, M. Leok, and N. H. McClamroch, “Geometric tracking control of a quadrotor UAV on SE(3),” CDC 2010.
