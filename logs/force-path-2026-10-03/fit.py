import csv,sys,numpy as np
r=list(csv.DictReader(open(sys.argv[1]))); t=np.array([float(x['sim_time_s']) for x in r]); z=np.array([float(x['z_m']) for x in r]); t-=t[0]
air=z>0.06; t,z=t[air],z[air]
pre=(t>0.04)&(t<0.22); c=np.polyfit(t[pre],z[pre],2); print("free-fall a=%.5f (n=%d)"%(2*c[0],pre.sum()))
post=t>float(sys.argv[2]); c=np.polyfit(t[post],z[post],2); print("powered a=%.5f m/s^2 over %.3f-%.3f s (n=%d)"%(2*c[0],t[post][0],t[post][-1],post.sum()))
# command arrival: last time residual vs free-fall < 1mm
cf=np.polyfit(t[pre],z[pre],2); res=z-np.polyval(cf,t); i=np.argmax(np.abs(res)>1e-3); print("departure from free fall (>1 mm) at t=%.3f s, z=%.4f"%(t[i],z[i]))
print("min z airborne %.4f at t=%.3f; final %.4f"%(z.min(),t[np.argmin(z)],z[-1]))
