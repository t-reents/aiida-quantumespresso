---
title: "Units Table: QE output, QE XML and Parser Comparison"
---

# Quantities and their Units

In the following table, the different units implemented in Quantum ESPRESSO output, the Quantum ESPRESSO XML file, and the parser are discussed. In Quantum ESPRESSO output, atomic units (rydberg for energies and bohr for lengths) are consistently followed, except for the fermi energy where eV is used. In the XML output of Quantum ESPRESSO, hartree units are followed for energies and bohr for lengths, whereas in the parser, the use of eV for energies and angstroms for lengths is implemented. The table below presents the different quantities discussed and their corresponding units for the three output methods.


| Quantity                 | Quantum Espresso Output | Quantum Espresso XML | Parser       |
| :----------------------: | :----------------------: | :------------------: | :----------: |
|      Cell dimensions     |           bohr           |         bohr         | Å    |
|        Total energy      |          Ry         |        Ha       |      eV      |
|      Energy accuracy     |          Ry         |        Ha       |      eV      |
|     Ewald contribution   |          Ry         |        Ha       |      eV      |
|    Hartree contribution  |          Ry         |        Ha       |      eV      |
|       One-center paw contribution   |          Ry         |       Ha      |      eV      |
|  One-electron contribution |        Ry         |       Ha      |      eV      |
|       XC contribution    |          Ry         | Ha |      eV      |
|        Fermi energy      |            eV            |        Ha       |      eV      |
|         Atomic positions        |   alat units [1]        |         bohr         |  Å    |
|       SCF accuracy       |          Ry         |        Ha       |      eV      |
|           Forces         |     $\frac{\text{Ry}}{\text{bohr}}$    |  $\frac{\text{Ha}}{\text{bohr}}$   | $\frac{\text{eV}}{\text{Å}}$ |
|        Total Force       |     $\frac{\text{Ry}}{\text{bohr}}$ | $\frac{\text{Ha}}{\text{bohr}}$ | $\frac{\text{eV}}{\text{Å}}$ |
|          Stress          |    $\frac{\text{Ry}}{\text{bohr}^3}$ | $\frac{\text{Ha}}{\text{bohr}^3}$ | GPa |




[1] Multiply with lattice constant; what you get is in bohr.
