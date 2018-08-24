# Set up steps for GPU visulization monitor totoal

## Purpose

For the purpose of intuitively monitoring the behavior of GPUs, we planed to produce a homemade visulization tool to better control over the status of GPUs by use of combination of [prometheus](https://prometheus.io/) and [grafana](https://grafana.com/) and docker container. Furthermore, we kept the concept of automation in mind, so we finished our task with automatically deploy service, load the dashboard and datasource.

## Version info

## DONE

- deploy the prometheus node exporter on the hypervisor.
- launch grafana & prometheus services on the docker container.
- make some critical metrics on the GPU info dashboard.
- launch a python program to get a metrics text file.

## TODO
- add some equally import metrics onto the dashboard (pciE, CUDA capability and so on).
- add the alert function.

## Installation Step

Prior to introduce how to install, we are going to explain to you why we treat node exporter so specially, i.e. why we deploy the node exporter on the hypervisor instead of deploying it with docker container as well. In fact, spinning up the node exporter on docker container makes definitely sense, but we have to set the docker runtime mode to nvidia-docker in order to retrieve the GPUs information which are attached to the hypervisor directly, more specifically ,it means if we don't change the runtime, we are not able to retrieve GPUs info with docker container. It should've been easy to set up the nvidia-docker as the runtime, but actually there is issue during the deployment caused by the incompatible version between the CUDA version and the vGPU driver version. So, we choose another way to go which is exactly the approach we used, set up the the node exporter on the hypervisor, and then record the text file on the hypervisor too. As for capturing data part, mounting the volume which include the metrics text file onto the prometheus container service, then work as conventional approach to transfer the data from prometheus to grafana.

For your information, we used to program to collect the metrics, one of them is homemade python program by working with *NVML* lib, and another one refered to the [nvidia_gpu_monitor](https://github.com/NVIDIA/gpu-monitoring-tools).

### Set up dcgm service

``` bash
$ sudo make install
$ sudo make exporter
```

### Set up the metrics collector python program
if you are using pipenv as well
``` bash
$ pipenv --python 3.6
$ pipenv shell
$ pipenv sync
$ python gputoolkit_metrics.py -q &
```
**Attention**: the *NVML* is a language-C lib, and it just get python binding on python2, so there's some incompatible issue by using this lib directly, such as `in line 1831 print c_count.value` classic incompatible version issues.


Otherwise, install the lib dependencies yourself which are described in the *Pipfile*, then run the python program.


### Deploy the containers
``` bash
$ docker-compose up -d
```

### Uninstall
``` bash
$ sudo make uninstall
```
