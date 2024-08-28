# RoCELib

RoCELib is a Python package intended to benchmark the different robust Counterfactual Explanation generation methods.
**Ro**bust **C**ounterfactual **E**xplanation **Lib**rary - RoCELib.

## Setup

In order to locally download this library, make sure to have `numpy`, `pandas`, `scikit-learn` and `pytest`.

If you have Conda installed you may prefer to use a virtual environment instead. First clone this repository. Then, inside
the repository, run these lines in Powershell or Cmd:

`conda create -n RoCELib python=3.9`

`conda activate RoCELib`

`conda install numpy pandas scikit-learn pytest`

`conda install pytorch torchvision torchaudio cpuonly -c pytorch`

`conda install tensorflow`

`conda install -c gurobi gurobi`

`conda install tqdm`

`conda install xgboost`

Gurobi gives free academic licenses.