import numpy as np
from scipy.optimize import curve_fit
import matplotlib.pyplot as plt

filename = "sampling_output.txt"
times = []
temperatures = []

with open(filename, "r") as f:
    next(f)
    for line in f:
        line = line.strip()
        if not line:
            continue
        t_str, temp_str = line.split(',')
        times.append(float(t_str))
        temperatures.append(float(temp_str))

times = np.array(times)
temperatures = np.array(temperatures)
def cooling_model(t, T_env, T0, tau):
    return T_env + (T0 - T_env) * np.exp(-t / tau)

T_env_guess = 100
T0_guess = temperatures[0]
tau_guess = (times[-1] - times[0]) / 2

popt, pcov = curve_fit(cooling_model, times, temperatures, p0=[T_env_guess, T0_guess, tau_guess], maxfev=5000)
T_env_fit, T0_fit, tau_fit = popt

print(f"T_env = {T_env_fit:.2f} °C")
print(f"T0    = {T0_fit:.2f} °C")
print(f"τ     = {tau_fit:.2f} s")
print(f"R^2 = {1 - np.sum((temperatures - cooling_model(times, *popt))**2) / np.sum((temperatures - np.mean(temperatures))**2):.4f}")

t_fit = np.linspace(times[0], times[-1], 300)
T_fit = cooling_model(t_fit, T_env_fit, T0_fit, tau_fit)


plt.plot(times, temperatures, "o", label="Measured")
plt.plot(t_fit, T_fit, "-", label="Fitted")
plt.xlabel("Time (s)")
plt.ylabel("Temperature (°C)")
plt.legend()
plt.show()
