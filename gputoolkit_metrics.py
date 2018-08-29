import argparse
import logging
import time
import platform
import os

from prometheus_client import CollectorRegistry, Gauge, write_to_textfile

from pynvml import *
import pycuda.driver as cd


def set_argument():
    parser = argparse.ArgumentParser(description="this service is used to collect gpu info," \
                                     " and give it back to grafana server for the purpose of visulization.")
    parser.add_argument('-v', '--verbose',
                        action='store_true',
                        help='turn on INFO model for logging instead of DEBUG model as default.')
    parser.add_argument('-t', '--collect_time',
                        help='set the sceraping time period, the unit is set as \'second\', ' \
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
    gputoolkit_device_num           = Gauge(prefix + "device_num",
                                            "gauge the device number in totoal",
                                            registry = registry)
    gputoolkit_nvdriver_version     = Gauge(prefix + "nvdriver_version",
                                            "found out the version nvidia "\
                                            "driver the gpu are using.",
                                            registry = registry)
    gputoolkit_cuda_runtime_version = Gauge(prefix + "cuda_runtime_version",
                                            "found out the cuda copmiler driver version "\
                                            "that the gpu are using.",
                                            registry = registry)
    gputoolkit_cuda_driver_version  = Gauge(prefix + "cuda_driver_version",
                                            "found out the cuda driver version the gpu are using.",
                                            registry = registry)
    gputoolkit_cuda_capability      = Gauge(prefix + "cuda_capability",
                                            "found out the cuda capability of the gpu are using. "\
                                            "Major/Minor version number",
                                            ['gpu', 'uuid'],
                                            registry = registry)
    gputoolkit_fan_speed            = Gauge(prefix + "fan_speed",
                                            "found out current fan speed for each gpu.",
                                            ['gpu', 'uuid'],
                                            registry = registry)
    gputoolkit_current_ecc_flag     = Gauge(prefix + "current_ecc_flag",
                                            "found out current ecc flag for each gpu," \
                                            "Toggle ECC support: 0/DISABLED, 1/ENABLED",
                                            ['gpu', 'uuid'],
                                            registry = registry)
    gputoolkit_pending_ecc_flag     = Gauge(prefix + "pending_ecc_flag",
                                            "found out pending ecc flag for each gpu," \
                                            "Toggle ECC support: 0/DISABLED, 1/ENABLED",
                                            ['gpu', 'uuid'],
                                            registry = registry)
    gputoolkit_attached_vgpu        = Gauge(prefix + "attached_vgpu",
                                            "list the gpu-vgpu map relation. the feedback" \
                                            " is its vgpu ID.",
                                            ['gpu', 'uuid', 'nth_vgpu'],
                                            registry = registry)
    gputoolkit_vgpu_license         = Gauge(prefix + "vgpu_license",
                                            "list the license of each vgpu.",
                                            ['gpu', 'uuid', 'nth_vgpu'],
                                            registry = registry)
    gputoolkit_vgpu_type            = Gauge(prefix + "vgpu_type",
                                            "list the instance type of each vgpu.",
                                            ['gpu', 'uuid', 'nth_vgpu'],
                                            registry = registry)
    gputoolkit_RX_pciE_speed        = Gauge(prefix + "RX_speed",
                                            "the realtime receive speed of current gpu.",
                                            ['gpu', 'uuid'],
                                            registry = registry)
    gputoolkit_TX_pciE_speed        = Gauge(prefix + "TX_speed",
                                            "the realtime transmit speed of current gpu.",
                                            ['gpu', 'uuid'],
                                            registry = registry)
    gputoolkit_pciE_cur_perfomance  = Gauge(prefix + "pciE_cur_perf",
                                            "the ideal current thresholds perfomance of pci " \
                                            "express of current device. The unit is GB/s",
                                            ['gpu', 'uuid'],
                                            registry = registry)
    gputoolkit_pciE_max_perfomance  = Gauge(prefix + "pciE_max_perf",
                                            "the ideal max thresholds perfomance of pci express" \
                                            " of current device. The unit is GB/s",
                                            ['gpu', 'uuid'],
                                            registry = registry)

    # pciE criteria GB/s
    pcie_criteria = {1: {1: 0.25,   2: 0.5,  4:1.0,  8:2.0,   16:4.0},
                     2: {1: 0.5,    2: 1.0,  4:2.0,  8:4.0,   16:8.0},
                     3: {1: 0.9846, 2: 1.97, 4:3.94, 8:7.88,  16:15.8},
                     4: {1: 1.969,  2: 3.94, 4:7.88, 8:15.75, 16:31.5}}

    try:
        nvmlInit()
    except Exception:
        raise NVML_ERROR_UNINITIALIZED

    # cuda complier/runtime version
    cuda_rt_version = cd.get_version()
    cuda_rt_version = "".join(str(i) for i in cuda_rt_version)
    cuda_rt_version = round(float(cuda_rt_version)/100, 2)
    log.info(f" the cuda complier/runtime version: {str(cuda_rt_version)}")
    gputoolkit_cuda_runtime_version.set(cuda_rt_version)

    # cuda driver version
    cuda_dr_version = cd.get_driver_version()
    log.info(f" the cuda driver version: {str(cuda_dr_version)}")
    gputoolkit_cuda_driver_version.set(cuda_dr_version)

    # attaced gpu account
    try:
        device_num = int(nvmlDeviceGetCount())
        gputoolkit_device_num.set(device_num)
        log.info(f" the current server get {device_num} gpu graphic card/cards in total.")
    except NVMLError:
        log.debug(" there're probably no usable GPU cards as attached.")

    #driver version
    driver_version = float(nvmlSystemGetDriverVersion())
    gputoolkit_nvdriver_version.set(driver_version)
    log.info(f" the version of nvidia dirver: {driver_version}")

    # for the purpose of making pycuda gpu retrieval module work,
    # the initializition is mandatory
    cd.init()

    # Retrieve one by one
    for i in range(device_num):
        # get gpu handle
        try:
            handle = nvmlDeviceGetHandleByIndex(i)
            uuid   = nvmlDeviceGetUUID(handle).decode('utf-8')
            name   = nvmlDeviceGetName(handle).decode('utf-8')
            log.info(f" Device {i}: {name}")
            log.info(f" Device uuid: {uuid}")
        except NVMLError:
            log.debug(" there're probably no usable GPU cards as attached.")

        # vGPU info
        try:
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
        except NVMLError:
            log.debug(" the vGPUs haven't been activated")

        # fan speed
        try:
            fan_speed = nvmlDeviceGetFanSpeed(handle)
            gputoolkit_fan_speed.labels(gpu=i, uuid=uuid).set(fan_speed)

            log.info(f" the fan speed of the current gpu: {fan_speed}%")
        except NVMLError:
            log.debug(" The reported speed is the intended fan speed." \
                      " If the fan is physically blocked and unable to spin," \
                      " the output will not match the actual fan speed.")

        # Ecc mode
        # Toggle ECC support: 0/DISABLED, 1/ENABLED
        # The "pending" ECC mode refers to the target mode following the next reboot.
        try:
            ecc_flag = nvmlDeviceGetEccMode(handle)
            gputoolkit_current_ecc_flag.labels(gpu=i, uuid=uuid).set(ecc_flag[0])
            gputoolkit_pending_ecc_flag.labels(gpu=i, uuid=uuid).set(ecc_flag[1])
            log.info(f" the current ecc mode: {ecc_flag[0]}, the pending ecc mode: {ecc_flag[1]}.")
        except NVMLError:
            log.debug(" Only applicable to devices with ECC")

        # cuda capability
        # driver_instance.compute_capability() -> tuple (major, minor)
        driver_instance = "".join(str(i) for i in cd.Device(i).compute_capability())
        driver_instance = round(float(driver_instance)/10, 2)
        gputoolkit_cuda_capability.labels(gpu=i, uuid=uuid) \
                                  .set(driver_instance)
        log.info(f" the cuda capability is: {driver_instance}")

        # pciE info
        try:
            # pciE link width
            # Retrieves the maximum PCIe link width possible with this device and system
            # I.E. for a device with a 16x PCIe bus width attached to a 8x PCIe system bus this function will report a max link width of 8.
            pcie_max_width = nvmlDeviceGetMaxPcieLinkWidth(handle)
            pcie_max_gen   = nvmlDeviceGetMaxPcieLinkGeneration(handle)
            gputoolkit_pciE_max_perfomance.labels(gpu=i, uuid=uuid) \
                                          .set(pcie_criteria[pcie_max_gen][pcie_max_width])
            log.info(f" the maximum pciE width info of current gpu: x{pcie_max_width}.")
            log.info(f" the maximum pciE generation of cuurent gpu: {pcie_max_gen}.")
            log.info(f" the maximul ideal transmit speed of current gpu: " \
                     f"{pcie_criteria[pcie_max_gen][pcie_max_width]}GB/s")


            # Retrieves the current PCIe link width
            pcie_cur_width = nvmlDeviceGetCurrPcieLinkWidth(handle)
            pcie_cur_gen   = nvmlDeviceGetMaxPcieLinkGeneration(handle)
            gputoolkit_pciE_cur_perfomance.labels(gpu=i, uuid=uuid) \
                                          .set(pcie_criteria[pcie_cur_gen][pcie_cur_width])
            log.info(f" the current pciE width info of current gpu: x{pcie_cur_width}.")
            log.info(f" the current pciE generation of cuurent gpu: {pcie_cur_gen}.")
            log.info(f" the current ideal transmit speed of current gpu: " \
                     f"{pcie_criteria[pcie_cur_gen][pcie_cur_width]}GB/s")

            # Retrieve the PCIe real time receive transmit speed, the unit is KB/s
            RX_speed = nvmlDeviceGetPcieThroughput(handle, NVML_PCIE_UTIL_RX_BYTES)
            TX_speed = nvmlDeviceGetPcieThroughput(handle, NVML_PCIE_UTIL_TX_BYTES)
            gputoolkit_RX_pciE_speed.labels(gpu=i, uuid=uuid).set(RX_speed)
            gputoolkit_TX_pciE_speed.labels(gpu=i, uuid=uuid).set(TX_speed)
            log.info(f' rx speed: {RX_speed}KB/s.')
            log.info(f' tx speed: {TX_speed}KB/s.')

        except NVMLError:
            log.debug(" pciE info cannot retrieve.")

    write_to_textfile("/run/prometheus/gputoolkit.prom", registry=registry)
    # write_to_textfile("/home/jfu/gpu_moni/gputoolkit.prom", registry=registry)

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

