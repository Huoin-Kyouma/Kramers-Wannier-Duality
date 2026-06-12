# Kramers-Wannier Duality on a Quantum Computer

This repository provides quantum circuits and simulation scripts to verify the Kramers-Wannier duality on a quantum computer/simulator. It is based upon the paper:
**"Quantum Operations for Kramers-Wannier duality"** ([arXiv:2405.09361](https://doi.org/10.48550/arXiv.2405.09361)).

The quantum circuits are evaluated using both the ideal `AerSimulator` and a hardware emulator representing the **IBM-Fez** backend (`FakeFez`).

## The Duality Identity

We verify the Kramers-Wannier duality in the sense of Eq. (38) of the paper, which establishes a trace identity between expectations on the domain-wall (dual) lattice and the original Ising lattice:

$$\text{Tr}_{\hat{\mathcal{H}}} \left( \hat{Z}_1 \hat{Z}_2 \mathcal{D}(\rho) \right) = \frac{1}{4} \text{Tr}_{\mathcal{H}} \left( X_1 P \rho \right)$$

Here, the left-hand side (LHS) is computed by preparing a state $\rho$, applying the duality operator $\mathcal{D}$, and measuring $\langle Z_1 Z_2 \rangle$ under charge symmetry projections. The right-hand side (RHS) measures the Ising expectation $\langle X_1 \rangle$ under the projection $P$. The ideal ratio between the two traces (LHS / RHS) is expected to be $\approx 0.25$.

---

## File Structure & Implementations

The repository contains two distinct implementations of the verification workflow:

### 1. `Verify_KW_duality.ipynb`
An interactive Jupyter Notebook that serves as a tutorial/walkthrough.
* **Backend:** Local `AerSimulator`.
* **Projection Method:** Uses Qiskit's `Operator` class to define projection matrices mathematically, then appends them as custom unitary matrices.
* **Execution:** Executed via legacy Qiskit APIs (`backend.run()`) for a fixed size ($n=6$) and fixed shot count ($2^{16}$).

### 2. `simulation.py`
A robust, parameterized, and hardware-ready command-line script.
* **Backend:** Supports both ideal simulators (`aer_simulator`) and hardware emulators (specifically targeting the **IBM-Fez** backend via `FakeFez`).
* **Projection Method:** Implements the $X$-parity projection entirely using standard quantum gates (Hadamard and CNOT gates), making the circuit executable on real/emulated quantum hardware.
* **Execution:** Utilizes the modern **Qiskit Runtime V2 Sampler** (`SamplerV2`) and transpiles circuits using `PresetPassManager` (optimization level 3).
* **Error Mitigation:** Integrates **M3 (Matrix-free Measurement Mitigation)** to correct readout errors, which is essential when executing on noisy hardware emulators.
* **Automation:** Loops over multiple runs, either fixing a single random state or generating a new state per run. It saves results to a `.npz` file and plots a PDF graph of the duality ratios across runs.

### 3. `script.sh`
A bash script that automates a comprehensive experimental sweep. It loops through:
* State evaluation modes (Same State vs. Different States)
* Backends (`aer` simulator vs. **IBM-Fez** `fake` emulator)
* Lattice sizes ($n = 2, 3, 4, 5$)
* Appropriate shot schedules for each configuration.

---

## Getting Started

### Prerequisites

Ensure you have Python 3 and the required libraries installed:
```bash
pip install qiskit qiskit-aer qiskit-ibm-runtime mthree numpy matplotlib
```

### Running the Code

#### 1. Interactive Notebook
Simply open the Jupyter Notebook and execute all cells:
```bash
jupyter notebook Verify_KW_duality.ipynb
```

#### 2. Command-Line Simulation Script (`simulation.py`)
You can run the script manually with custom arguments:
```bash
python3 simulation.py <n_qubits> <shots> <backend_type> <use_same_state> <num_runs>
```
* **`<n_qubits>`**: Number of lattice qubits (default: `4`)
* **`<shots>`**: Number of measurement shots (default: `20000`)
* **`<backend_type>`**: `'aer'` for ideal simulation, `'fake'` for FakeFez hardware emulation (default: `'aer'`)
* **`<use_same_state>`**: `'true'` to use the same random state across runs, `'false'` to generate a new state for each run (default: `'true'`)
* **`<num_runs>`**: Number of simulation runs (default: `5`)

Example:
```bash
python3 simulation.py 4 100000 fake true 10
```

This will run the simulation, apply M3 mitigation, print out the mitigated expectations, and output:
1. A plot file: `N_N=4_S=100000_B=fake_Mode=Same_Runs=10.pdf`
2. A data file: `results_N=4_S=100000_B=fake_Mode=Same_Runs=10.npz`

#### 3. Running on a Real Hardware Backend
To execute the simulation on an actual IBM Quantum hardware backend instead of a simulator/emulator:
1. Open `simulation.py`.
2. Locate the `# Initialize Backend` block (around lines 29-35).
3. Update it to initialize `QiskitRuntimeService` and specify a real hardware device:
   ```python
   from qiskit_ibm_runtime import QiskitRuntimeService

   # Initialize Qiskit Runtime Service (uses saved credentials/tokens)
   service = QiskitRuntimeService()

   # Retrieve a real hardware backend
   backend = service.backend("ibm_kyoto")  # replace with an active backend name
   ```
4. Run the script as usual. The pipeline will automatically transpile the circuits to the physical device layout and calibrate M3 error mitigation for that specific hardware.

#### 4. Automated Sweep Script (`script.sh`)
To run the full grid search of parameters across both ideal simulation and fake hardware:
```bash
chmod +x script.sh
./script.sh
```
This sweeps sizes $n \in \{2, 3, 4, 5\}$ and both backends, saving plots and `.npz` data for all sweeps.

