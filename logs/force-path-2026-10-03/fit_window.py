"""Fit powered a_z from departure-from-free-fall + 0.12 s (rotors >99% spun up) until z first drops below 0.15 m."""
import csv,sys,numpy as np
r=list(csv.DictReader(open(sys.argv[1]))); t=np.array([float(x['sim_time_s']) for x in r]); z=np.array([float(x['z_m']) for x in r]); t-=t[0]
pre=(t>0.04)&(t<0.22); cf=np.polyfit(t[pre],z[pre],2); dep=t[np.argmax(np.abs(z-np.polyval(cf,t))>1e-3)]
low=np.argmax(z<0.15) if (z<0.15).any() else len(z); end=t[low-1]
w=(t>=dep+0.12)&(t<=end); c=np.polyfit(t[w],z[w],2)
print(f"departure {dep:.3f} s; powered window {t[w][0]:.3f}-{t[w][-1]:.3f} s (n={w.sum()}); a_z={2*c[0]:+.5f} m/s^2")
