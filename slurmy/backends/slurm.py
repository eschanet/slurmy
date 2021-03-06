
import subprocess
import os
import shlex
import logging
from ..tools.defs import Status
from .base import Base
from .defs import bids
from ..tools import options

log = logging.getLogger('slurmy')


class Slurm(Base):
    """@SLURMY
    Slurm backend class. Inherits from the Base backend class.

    * `name` Name of the parent job.
    * `log` Log file written by slurm.
    * `run_script` The script that is executed on the worker node.
    * `run_args` Run arguments that are passed to the run_script.

    Slurm batch submission arguments (see slurm documentation):

    * `partition` Partition on which the slurm job is running.
    * `exclude` Worker node(s) that should be excluded.
    * `clusters` Cluster(s) in which the slurm job is running.
    * `qos` Additional quality of service setting.
    * `mem` Memory limit for the slurm job.
    * `time` Time limit for the slurm job.
    * `export` Environment exports that are propagated to the slurm job.
    """

    bid = bids['SLURM']
    _script_options_identifier = 'SBATCH'
    _commands = ['sbatch', 'scancel', 'sacct']
    _successcode = '0:0'
    _run_states = set(['PENDING', 'RUNNING'])

    def __init__(self, name = None, log = None, run_script = None, run_args = None, partition = None, exclude = None, clusters = None, qos = None, mem = None, time = None, export = None):
        super(Slurm, self).__init__()
        ## Common backend options
        self.name = name
        self.log = log
        self.run_script = run_script
        self.run_args = run_args
        ## Batch options
        self.partition = partition
        self.clusters = clusters
        self.qos = qos
        self.exclude = exclude
        self.mem = mem
        self.time = time
        self.export = export
        ## Internal variables
        self._job_id = None
        self._exitcode = None

    def submit(self):
        """@SLURMY
        Submit the job to the slurm batch system.

        Returns the job id (int).
        """
        submit_list = self._get_submit_command()
        log.debug('({}) Submit job with command {}'.format(self.name, submit_list))
        submit_string = subprocess.check_output(submit_list, universal_newlines = True)
        job_id = int(submit_string.split(' ')[3].rstrip('\n'))
        self._job_id = job_id

        return job_id

    def cancel(self):
        """@SLURMY
        Cancel the slurm job.
        """
        log.debug('({}) Cancel job'.format(self.name))
        cancel_command = 'scancel {}'.format(self._job_id)
        ## Wrap command
        cancel_command = Base._get_command(cancel_command, Slurm.bid)
        os.system(cancel_command)

    def status(self):
        """@SLURMY
        Get the status of slurm job from sacct entry.

        Returns the job status (Status).
        """
        sacct_return = self._get_sacct_entry('Job,State,ExitCode')
        status = Status.RUNNING
        if sacct_return is not None:
            job_state = sacct_return['finished']
            # if job_state not in Slurm._run_states and 'success' in sacct_return:
            if job_state not in Slurm._run_states:
                status = Status.FINISHED
                self._exitcode = sacct_return['success']

        return status

    def exitcode(self):
        """@SLURMY
        Get the exitcode of slurm job from sacct entry. Evaluation is actually done by Slurm.status(), Slurm.exitcode() only returns the value. If exitcode at this stage is None, execute Slurm.status() beforehand.

        Returns the job exitcode (str).
        """
        ## If exitcode is not set yet, run status evaluation
        if self._exitcode is None:
            self.status()

        return self._exitcode

    def _get_submit_command(self):
        submit_command = 'sbatch '
        if self.name: submit_command += '-J {} '.format(self.name)
        if self.log: submit_command += '-o {} '.format(self.log)
        if self.partition: submit_command += '-p {} '.format(self.partition)
        if self.exclude: submit_command += '-x {} '.format(self.exclude)
        if self.clusters: submit_command += '-M {} '.format(self.clusters)
        if self.qos: submit_command += '--qos={} '.format(self.qos)
        if self.mem: submit_command += '--mem={} '.format(self.mem)
        if self.time: submit_command += '--time={} '.format(self.time)
        if self.export: submit_command += '--export={} '.format(self.export)
        ## Add run_script setup through wrapper
        run_script = self.wrapper.get(self.run_script)
        submit_command += '{} '.format(run_script)
        ## Add run_args
        if self.run_args:
            if isinstance(self.run_args, str):
                submit_command += self.run_args
            else:
                submit_command += ' '.join(self.run_args)
        ## Wrap command
        submit_command = Base._get_command(submit_command, Slurm.bid)
        ## Split command string with shlex in a Popen digestable way
        submit_command = shlex.split(submit_command)

        return submit_command

    def _get_sacct_entry(self, column):
        sacct_command = Slurm._get_sacct_command(column, job_id = self._job_id, partition = self.partition, clusters = self.clusters)
        sacct_output = subprocess.check_output(sacct_command, universal_newlines = True).rstrip('\n').split('\n')
        log.debug('({}) Return list from sacct: {}'.format(self.name, sacct_output))
        sacct_return = None
        if len(sacct_output) > 1:
            sacct_return = {}
            for entry in sacct_output[1:]:
                job_string, state, exitcode = entry.split('|')
                ## Skip the .batch entry if it exists
                if '.batch' in job_string: continue
                log.debug('({}) Column "{}" values from sacct: {} {} {}'.format(self.name, column, job_string, state, exitcode))
                sacct_return['finished'] = state
                sacct_return['success'] = exitcode

        return sacct_return

    @staticmethod
    def _get_sacct_command(column, job_id = None, user = None, partition = None, clusters = None):
        sacct_command = 'sacct '
        if partition: sacct_command += '-r {} '.format(partition)
        if clusters: sacct_command += '-M {} '.format(clusters)
        if job_id: sacct_command += '-j {} '.format(job_id)
        if user: sacct_command += '-u {} '.format(user)
        sacct_command += '-P -o {}'.format(column)
        ## Wrap command
        sacct_command = Base._get_command(sacct_command, Slurm.bid)
        ## Split command string with shlex in a Popen digestable way
        sacct_command = shlex.split(sacct_command)

        return sacct_command

    @staticmethod
    def get_listen_func(partition = None, clusters = None):
        user = options.Main.user
        command = Slurm._get_sacct_command('JobID,State,ExitCode', user = user, partition = partition, clusters = clusters)
        ## Define function for Listener
        def listen(results, interval = 1):
            import subprocess, time
            from collections import OrderedDict
            while True:
                result = subprocess.check_output(command, universal_newlines = True).rstrip('\n').split('\n')
                return_states = {}
                return_exitcodes = {}
                job_ids = set()
                ## Evaluate sacct return values
                for res in result[1:]:
                    job_id, state, exitcode = res.split('|')
                    ## Skip the .batch entries if any exist
                    if '.batch' in job_id: continue
                    ## Skip the .extern entries if any exist
                    if '.extern' in job_id: continue
                    job_id = int(job_id)
                    job_ids.add(job_id)
                    return_states[job_id] = state
                    return_exitcodes[job_id] = exitcode
                ## Generate results dict
                res_dict = OrderedDict()
                for job_id in job_ids:
                    if return_states[job_id] in Slurm._run_states: continue
                    exitcode = return_exitcodes[job_id]
                    res_dict[job_id] = {'status': Status.FINISHED, 'exitcode': exitcode}
                results.put(res_dict)
                time.sleep(interval)

        return listen
