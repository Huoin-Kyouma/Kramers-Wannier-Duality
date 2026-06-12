from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister
from qiskit.circuit.library import TwoLocal
from qiskit_ibm_runtime.fake_provider import FakeFez
from qiskit.circuit import ParameterVector

import numpy as np
from numpy import pi
from matplotlib import pyplot as plt

from qiskit.transpiler.preset_passmanagers import generate_preset_pass_manager
from qiskit_ibm_runtime import SamplerV2 as Sampler
from qiskit_aer import Aer, AerSimulator


import mthree
import sys

# Argument 1: n, Argument 2: shots, Argument 3: backend_type ("aer" or "fake")
# Argument 4: use_same_state ("true" or "false"), Argument 5: num_runs
n = int(sys.argv[1]) if len(sys.argv) > 1 else 4
shot = int(sys.argv[2]) if len(sys.argv) > 2 else 20000
b_type = sys.argv[3] if len(sys.argv) > 3 else "aer"

# Parse the toggle and number of runs from bash
use_same_state_str = sys.argv[4].lower() if len(sys.argv) > 4 else "true"
use_same_state = (use_same_state_str == "true")
num_runs = int(sys.argv[5]) if len(sys.argv) > 5 else 5

# Initialize Backend
if b_type == "aer":
    backend = Aer.get_backend('aer_simulator')
    print(f"Running Ideal Simulation: N={n}, Shots={shot}")
else:
    backend = FakeFez()
    print(f"Running Hardware Emulation (FakeFez): N={n}, Shots={shot}")

mode_label = "Same" if use_same_state else "Diff"
prefix = f"N={n}_S={shot}_B={b_type}_Mode={mode_label}_Runs={num_runs}"

circuits = [] # This will store our two main circuits

# State Preparation
circ_for_ising = QuantumCircuit(n)
circ_for_ising.x(0)

# Create a vector of parameters instead of random numbers
num_params = 4 * n 
theta = ParameterVector('theta', num_params)

variational_form = TwoLocal(
    n,
    rotation_blocks=["rz", "ry"],
    entanglement_blocks="cx",
    entanglement="linear",
    reps=1,
    insert_barriers=True,
)

# Assign the symbolic ParameterVector to the variational form
variational_form = variational_form.assign_parameters(theta)

# The resulting ising_state is now fully parameterized
ising_state = circ_for_ising.compose(variational_form)


# Duality Gate Construction
ising = QuantumRegister(n, "ising")  
dwall = QuantumRegister(n, "dwall")  
qc = QuantumCircuit(ising, dwall)

qc.ryy(-pi/2, ising[n-1], dwall[n-1]) 
qc.rxx(-pi/2, ising[n-1], dwall[n-1])

for qbit in range(n-2, -1, -1):
    qc.swap(ising[qbit], dwall[qbit])

qc.rx(-pi/2, dwall[n-1])

for qbit in range(n-2, -1, -1):
    qc.rzz(-pi/2, dwall[qbit], dwall[qbit+1])
    qc.rx(-pi/2, dwall[qbit])

duality_gate = qc.to_gate(label="CS")  

# Efficient Projection Definition
def apply_x_parity_projection(circuit, lattice_qubits, ancilla_qubit):
    for q in lattice_qubits:
        circuit.h(q)
    for q in lattice_qubits:
        circuit.cx(q, ancilla_qubit)
    for q in lattice_qubits:
        circuit.h(q)

# 
#  Dual Circuit Assembly
ising = QuantumRegister(n, "ising")  
dwall = QuantumRegister(n, "dwall")  
ancilla_is = QuantumRegister(2, "ancilla_is")
ancilla_dw = QuantumRegister(2, "ancilla_dw")
meas_reg = ClassicalRegister(4+n, "meas_reg") 

qc_dual = QuantumCircuit(ising, dwall, ancilla_is, ancilla_dw, meas_reg)
qc_dual.compose(ising_state, qubits=ising[:], inplace=True)
qc_dual.barrier()

apply_x_parity_projection(qc_dual, ising[:], ancilla_is[0])
apply_x_parity_projection(qc_dual, dwall[:], ancilla_dw[0])
qc_dual.barrier()

qc_dual.append(duality_gate, (ising[:] + dwall[:]))
qc_dual.barrier()

apply_x_parity_projection(qc_dual, ising[:], ancilla_is[1])
apply_x_parity_projection(qc_dual, dwall[:], ancilla_dw[1])
qc_dual.barrier()

qc_dual.measure(ancilla_is[0], meas_reg[0])
qc_dual.measure(ancilla_dw[0], meas_reg[1]) 
qc_dual.measure(ancilla_is[1], meas_reg[2])
qc_dual.measure(ancilla_dw[1], meas_reg[3]) 
qc_dual.measure(dwall[:], meas_reg[4:4+n])

circuits.append(qc_dual)


# Ising Circuit Assembly
ising = QuantumRegister(n, "ising")  
ancilla_is = QuantumRegister(1, "ancilla_is")
meas_reg = ClassicalRegister(n+1, "meas_reg")                                           

qc_ising = QuantumCircuit(ising, ancilla_is, meas_reg)
qc_ising.compose(ising_state, qubits=ising[:], inplace=True)
qc_ising.barrier()

apply_x_parity_projection(qc_ising, ising[:], ancilla_is[0])
qc_ising.barrier()

qc_ising.h(ising[0])  
qc_ising.barrier()

qc_ising.measure(ising[:], meas_reg[:n])
qc_ising.measure(ancilla_is[0], meas_reg[n])

circuits.append(qc_ising)

# Hardware & Mitigation Setup
pm = generate_preset_pass_manager(backend=backend, optimization_level=3)
sampler = Sampler(backend)

# 1. Transpile to ISA 
isa_circ_dual = pm.run(circuits[0])
isa_circ_ising = pm.run(circuits[1])

# 2. Extract final physical measurement mappings
mapping_dual = mthree.utils.final_measurement_mapping(isa_circ_dual)
mapping_ising = mthree.utils.final_measurement_mapping(isa_circ_ising)

# 3. Calibrate M3 using the physical qubits chosen by the transpiler
mit = mthree.M3Mitigation(backend)
mit.cals_from_system(mapping_dual)

# Functions for Data Extraction
def dw_expectation_from_counts(counts, shot, n):
    dw_value = 0
    for key, value in counts.items():
        bits = key
        L = len(bits)

        anc_is0 = bits[L-1-0]
        anc_dw0 = bits[L-1-1]
        anc_is1 = bits[L-1-2]
        anc_dw1 = bits[L-1-3]
        dw0 = bits[L-1-(4+0)]
        dw1 = bits[L-1-(4+1)]

        if anc_is0 == '0' and anc_dw0 == '0' and anc_is1 == '0' and anc_dw1 == '0':
            if dw0 == dw1:
                dw_value += value
            else:
                dw_value -= value
    return dw_value / shot

def ising_expectation_from_counts(counts, shot, n):
    P_0 = P_1 = 0.0
    for key, value in counts.items():
        bits = key
        L = len(bits)
        anc = bits[L-1-n]
        is0 = bits[L-1-0]

        if anc == '0':
            if is0 == '0':
                P_0 += value / shot
            else:
                P_1 += value / shot
    return P_0 - P_1

# Executor Functions 
def executor_dw(isa_circ):
    job = sampler.run([isa_circ], shots=shot)
    result = job.result()
    raw_counts = result[0].data.meas_reg.get_counts()
    
    quasi = mit.apply_correction(raw_counts, mapping_dual)  
    mitigated_counts = {bit: prob * shot for bit, prob in quasi.items()}
    return dw_expectation_from_counts(mitigated_counts, shot, n)

def executor_ising(isa_circ):
    job = sampler.run([isa_circ], shots=shot)
    result = job.result()
    raw_counts = result[0].data.meas_reg.get_counts()
    
    quasi = mit.apply_correction(raw_counts, mapping_ising)
    mitigated_counts = {bit: prob * shot for bit, prob in quasi.items()}
    return ising_expectation_from_counts(mitigated_counts, shot, n)


raw_ratios = []


if use_same_state:
    print("Mode: Evaluating the SAME state across all runs.")
    fixed_parameters = 2 * np.pi * np.random.rand(num_params)
    
    bound_isa_dual = isa_circ_dual.assign_parameters(fixed_parameters)
    bound_isa_ising = isa_circ_ising.assign_parameters(fixed_parameters)
else:
    print("Mode: Evaluating a DIFFERENT random state for each run.")


for run in range(num_runs):
    print(f"\n================ RUN {run + 1} / {num_runs} ================")

    if not use_same_state:
        current_parameters = 2 * np.pi * np.random.rand(num_params)
        bound_isa_dual = isa_circ_dual.assign_parameters(current_parameters)
        bound_isa_ising = isa_circ_ising.assign_parameters(current_parameters)


    raw_dw = executor_dw(bound_isa_dual)        
    raw_ising = executor_ising(bound_isa_ising)  
    
    # Avoid division by zero if expectation value is exactly 0
    if raw_ising == 0:
        raw_ratio = np.nan
        print("Warning: Ising expectation is 0, ratio undefined.")
    else:
        raw_ratio = raw_dw / raw_ising

    print("\n--- M3-mitigated results ---")
    print("⟨Z0Z1⟩ dual (raw)   =", raw_dw)
    print("⟨X0⟩ ising (raw)    =", raw_ising)
    print("Raw ratio           =", raw_ratio)

    raw_ratios.append(raw_ratio)

# %% Plotting the Results
ratio_ideal = 0.25
plt.figure(figsize=(9,5))
plt.plot(raw_ratios, 'o-', label='M3-mitigated')
plt.axhline(ratio_ideal, color='black', linestyle=':', label=f'Ideal ratio = {ratio_ideal:.3f}')
plt.xlabel('Trial number')
plt.ylabel('Dual / Ising ratio')
plt.title(f'Kramers–Wannier Duality Ratio on {prefix}')
plt.legend()
plt.grid(True)
plt.tight_layout()
plt.savefig(f"N_{prefix}.pdf")


# %%
np.savez(f"results_{prefix}.npz", raw_ratios=raw_ratios)


