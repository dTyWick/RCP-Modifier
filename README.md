# RCP-Modifier
Change the concentration of fossil fuel-produced CO2 in various RCP pathways and observe how the MAGICC model updates its predictions for global surface temperatures.

## Installation + Running the Program
One should create an anaconda environment based off of *environment.yml*, with the command 

```
conda env create -f environment.yml
```
where the yml file has been provided in the repository. Now, pymagicc runs off of a compiled Windows binary, so if you are on Linux or OS X, go to the [pymaggic github page](https://github.com/openscm/pymagicc) in order to learn how to run it. This process involves installing wine,a compatability layer between Windows and Linux/OS X.

Once this is done, one can simply run

```
python climate_app.py
```
and enjoy!
