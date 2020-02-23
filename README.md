# SLURMY - Special handLer for Universal Running of Multiple jobs, Yes!

Slurmy is a general batch submission module, which allows to define very general jobs to be run on batch system setups on linux computing clusters. Currently, only Slurm and HTCondor are supported as backends, but further backends can easily be added. The definition of the job execution is done with a general shell execution script, as is used by most batch systems. In addition to the batch definition, jobs can also be dynamically executed locally, which allows for an arbitrary combination of batch and local jobs.

Please have a look at the [documentation page](https://eschanet.github.io/slurmy/) for more information.

### DISCLAIMER

This is a fork of the [original slurmy project](https://github.com/Thomas-Maier/slurmy) developed by Thomas Maier, which&mdash;due to the author leaving the research group&mdash;is not being maintained anymore.
