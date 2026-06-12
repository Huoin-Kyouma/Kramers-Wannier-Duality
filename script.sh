#!/bin/bash

# --- CONFIGURATION ---
backends=("aer" "fake")
lattice_sizes=(2 3 4 5)
state_modes=("true" "false")  # Iterates through both Same State (true) and Different States (false)
NUM_RUNS=5                    # Number of runs per specific configuration

for mode in "${state_modes[@]}"
do
   echo "================================================================"
   echo " MODE: USE_SAME_STATE = $mode "
   echo "================================================================"
   
   for b in "${backends[@]}"
   do
      echo "----------------------------------------"
      echo " BACKEND: $b "
      echo "----------------------------------------"
      
      for n in "${lattice_sizes[@]}"
      do
         # Determine shots (s)
         if [ "$b" == "aer" ]; then
            s=20000000  # High shot count for ideal simulation stability
         else
            # Hardware-specific shot schedule for FakeFez
            case $n in
               2) s=100000 ;;
               3) s=100000 ;;
               4) s=100000 ;;
               5) s=100000 ;;
            esac
         fi
         
         echo "Running: N=$n, Shots=$s, Backend=$b, Mode=$mode, Runs=$NUM_RUNS"
         
         # Execute the Python script with all 5 arguments
         python3 simulation.py $n $s $b $mode $NUM_RUNS
         
      done
   done
done

echo "Comprehensive experimental sweep (Same & Different states) completed."
