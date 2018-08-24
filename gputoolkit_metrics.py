import argparse
import logging
import time
import platform
import os

from prometheus_client import CollectorRegistry, Gauge, write_to_textfile
from prometheus_client import start_http_server, core

from pynvml import *
# from numba import cuda


def set_argument():
    parser = argparse.ArgumentParser(description="this service is used to collect gpu info," \
                                     " and give it back to grafana server for the purpose of visulization.")
    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help='turn on INFO model for logging instead of DEBUG model as default.')
    parser.add_argument('-t', '--collect_time',
                        help='set the sceraping time period, the unit is set as second, ' \
                        "if set nothing, the porgram is going to scrape every 1 sec by default",
                        type=int,
                        default=1)
    parser.add_argument('-q', '--quiet',
                        help='set script on silence mode, no logging info.',
                        action="store_true")

    return parser


def gpu_info_retrieval(parser):
    # give a prefix to the variable
    prefix = "gputoolkit_"

    # set logging
    args = parser.parse_args()
    log = logging.getLogger('gputoolkit')
    if not args.quiet:
        logging.basicConfig(level=logging.DEBUG if args.verbose else logging.INFO)


    # initialize gauge variable
    registry = CollectorRegistry()
    gputoolkit_device_num       = Gauge(prefix + "device_num",
                                        "gauge the device number in totoal",
                                        registry = registry)
    gputoolkit_nvdriver_version = Gauge(prefix + "nvdriver_version",
                                        "found out the version nvidia "\
                                        "driver the gpu are using.",
                                        registry = registry)
    # gputoolkit_cuda_version     = Gauge(prefix + "cuda_version",
    #                                     "found out the cuda version the gpu are using.",
    #                                     registry = registry)
    # gputoolkit_cuda_capability  = Gauge(prefix + "cuda_version",
    #                                     "found out the cuda version the gpu are using.",
    #                                     registry = registry)
    gputoolkit_fan_speed        = Gauge(prefix + "fan_speed",
                                        "found out current fan speed for each gpu.",
                                        ['gpu', 'uuid'],
                                        registry = registry)
    gputoolkit_current_ecc_flag = Gauge(prefix + "current_ecc_flag",
                                        "found out current ecc flag for each gpu," \
                                        "Toggle ECC support: 0/DISABLED, 1/ENABLED",
                                        ['gpu', 'uuid'],
                                        registry = registry)
    gputoolkit_pending_ecc_flag = Gauge(prefix + "pending_ecc_flag",
                                        "found out pending ecc flag for each gpu," \
                                        "Toggle ECC support: 0/DISABLED, 1/ENABLED",
                                        ['gpu', 'uuid'],
                                        registry = registry)
    gputoolkit_attached_vgpu    = Gauge(prefix + "attached_vgpu",
                                        "list the gpu-vgpu map relation. the feedback" \
                                        " is its vgpu ID.",
                                        ['gpu', 'uuid', 'nth_vgpu'],
                                        registry = registry)
    gputoolkit_vgpu_license     = Gauge(prefix + "vgpu_license",
                                        "list the license of each vgpu.",
                                        ['gpu', 'uuid', 'nth_vgpu'],
                                        registry = registry)
    gputoolkit_vgpu_type        = Gauge(prefix + "vgpu_type",
                                        "list the instance type of each vgpu.",
                                        ['gpu', 'uuid', 'nth_vgpu'],
                                        registry = registry)

    try:
        nvmlInit()
    except Exception:
        raise NVML_ERROR_UNINITIALIZED

    # cuda version
    # cuda_path = '/usr/local/cuda/version.txt'
    # if os.path.isfile(cuda_path):
    #     with open("/usr/local/cuda/version.txt", 'r') as f:
    #         cuda_version = f.read()
    #         log.info(f" the cuda version: {cuda_version}.")
    # else:
    #     raise FileNotFoundError

    # cuda version -> NameError: name 'nvmlSystemGetCudaDriverVersion' is not defined
    # cuda_version = nvmlSystemGetCudaDriverVersion()
    # log.info(f"the cuda version of the current gpu is {cuda_version}")

    # cuda capability
    # install both CUDA & numba
    # gpu = cuda

    # attaced gpu account
    device_num = int(nvmlDeviceGetCount())
    gputoolkit_device_num.set(device_num)
    # write_to_textfile('/home/jfu/test_textfile', registry)
    log.info(f" the current server get {device_num} gpu graphic card/cards in total.")

    # nvml_version = nvmlSystemGetNVMLVersion()
    # log.info(f" the version of nvml: {nvml_version}")

    #driver version
    driver_version = float(nvmlSystemGetDriverVersion())
    gputoolkit_nvdriver_version.set(driver_version)
    log.info(f" the version of nvidia dirver: {driver_version}")

    for i in range(device_num):
        # Retrieve one by one
        handle = nvmlDeviceGetHandleByIndex(i)
        uuid   = nvmlDeviceGetUUID(handle).decode('utf-8')
        name   = nvmlDeviceGetName(handle).decode('utf-8')
        log.info(f" Device {i}: {name}")
        log.info(f" Device uuid: {uuid}")

        vgpu_num = len(nvmlDeviceGetActiveVgpus(handle))
        vgpu_id  = nvmlDeviceGetActiveVgpus(handle)
        log.info(f" {vgpu_num} vgpus attached to current device.")

        vgpu_list = []
        for active_vgpu in range(vgpu_num):
            gputoolkit_attached_vgpu.labels(gpu=i, uuid=uuid, nth_vgpu=active_vgpu) \
                                    .set(int(vgpu_id[active_vgpu]))
            vgpu_list.append(int(vgpu_id[active_vgpu]))

        for instance in vgpu_id:

            # vgpu license status
            license = nvmlVgpuInstanceGetLicenseStatus(instance)
            gputoolkit_vgpu_license.labels(gpu=i, uuid=uuid, nth_vgpu=vgpu_list \
                                   .index(instance)).set(license)
            log.info(f' the license status of current vgpu: {license}.')

            # vgpu Instance type
            instance_type = nvmlVgpuInstanceGetType(instance)
            gputoolkit_vgpu_type.labels(gpu=i, uuid=uuid, nth_vgpu=vgpu_list \
                                .index(instance)).set(instance_type)
            log.info(f' the instance type of current vgpu: {instance_type}.')

        # fan speed
        try:
            fan_speed = nvmlDeviceGetFanSpeed(handle)
            gputoolkit_fan_speed.labels(gpu=i, uuid=uuid).set(fan_speed)

            log.info(f" the fan speed of the current gpu: {fan_speed}%")
        except Exception:
            gputoolkit_fan_speed.labels(gpu=i, uuid=uuid).set(0)
            log.debug(" The reported speed is the intended fan speed." \
                      "If the fan is physically blocked and unable to spin," \
                      " the output will not match the actual fan speed.")

        # Ecc mode
        # Toggle ECC support: 0/DISABLED, 1/ENABLED
        ecc_flag = nvmlDeviceGetEccMode(handle)
        gputoolkit_current_ecc_flag.labels(gpu=i, uuid=uuid).set(ecc_flag[0])
        gputoolkit_pending_ecc_flag.labels(gpu=i, uuid=uuid).set(ecc_flag[1])
        log.info(f" the current ecc mode: {ecc_flag[0]}, the pending ecc mode: {ecc_flag[1]}")

        # cuda capability -> NameError: name 'nvmlDeviceGetCudaComputeCapability' is not defined
        # cuda_capab = nvmlDeviceGetCudaComputeCapability(handle)
        # log.info(f"the cuda capability of current gpu: {cuda_capab}.")

        # pciE link width
        # Retrieves the maximum PCIe link width possible with this device and system
        # I.E. for a device with a 16x PCIe bus width attached to a 8x PCIe system bus this function will report a max link width of 8.
        pcie_max_width = nvmlDeviceGetMaxPcieLinkWidth(handle)
        log.info(f" the maximum pciE width info of current gpu: x{pcie_max_width}")

        # Retrieves the current PCIe link width
        pcie_cur_width = nvmlDeviceGetCurrPcieLinkWidth(handle)
        log.info(f" the current pciE width info of current gpu: x{pcie_cur_width}")

        write_to_textfile("/run/prometheus/gputoolkit.prom", registry=registry)

    try:
        nvmlShutdown()
    except Exception:
        raise NVML_ERROR_UNINITIALIZED


def main():
    parser = set_argument()
    args = parser.parse_args()
    while True:
        gpu_info_retrieval(parser)
        time.sleep(args.collect_time)


if __name__ == '__main__':
    main()

