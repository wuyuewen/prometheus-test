import prometheus_client
import re
from prometheus_client import Gauge,start_http_server,Counter
import pycurl
import time
import threading
from io import BytesIO
from utils.utils import runCmdRaiseException
from utils.libvirt_util import list_active_vms, get_disks_spec, get_vcpus, get_macs

vm_resource_utilization = Gauge('vm_resource_utilization', 'The resource utilization of virtual machine', \
                                ['cpu_metrics', 'mem_metrics', 'disks_metrics', 'networks_metrics'])

def collect_vm_metrics(vm):
    resource_utilization = {'cpu_metrics': {}, 'mem_metrics': {},
                            'disks_metrics': [], 'networks_metrics': []}
#     cpus = len(get_vcpus(vm)[0])
#     print(cpus)
    cpu_stats = runCmdRaiseException('virsh cpu-stats --total %s' % vm)
    cpu_time = 0.00
    cpu_system_time = 0.00
    cpu_user_time = 0.00
    for line in cpu_stats:
        if line.find('cpu_time') != -1:
            p1 = r'^(\s*cpu_time\s*)([\S*]+)\s*(\S*)'
            m1 = re.match(p1, line)
            if m1:
                cpu_time = float(m1.group(2))
        elif line.find('system_time') != -1:
            p1 = r'^(\s*system_time\s*)([\S*]+)\s*(\S*)'
            m1 = re.match(p1, line)
            if m1:
                cpu_system_time = float(m1.group(2))
        elif line.find('user_time') != -1:
            p1 = r'^(\s*user_time\s*)([\S*]+)\s*(\S*)'
            m1 = re.match(p1, line)
            if m1:
                cpu_user_time = float(m1.group(2))
    if cpu_time and cpu_system_time and cpu_user_time:
        resource_utilization['cpu_metrics']['cpu_system_rate'] = '%.2f' % (cpu_system_time / cpu_time)
        resource_utilization['cpu_metrics']['cpu_user_rate'] = '%.2f' % (cpu_user_time / cpu_time)
        resource_utilization['cpu_metrics']['cpu_idle_rate'] = \
        '%.2f' % (100 - ((cpu_user_time + cpu_system_time) / cpu_time))
    else:
        resource_utilization['cpu_metrics']['cpu_system_rate'] = '%.2f' % (0.00)
        resource_utilization['cpu_metrics']['cpu_user_rate'] = '%.2f' % (0.00)
        resource_utilization['cpu_metrics']['cpu_idle_rate'] = '%.2f' % (0.00)
    mem_stats = runCmdRaiseException('virsh dommemstat %s' % vm)
    mem_actual = 0.00
    mem_unused = 0.00
    mem_available = 0.00
    for line in mem_stats:
        if line.find('unused') != -1:
            mem_unused = float(line.split(' ')[1].strip())
            resource_utilization['mem_metrics']['mem_unused'] = '%.2f' % (mem_unused)
        elif line.find('available') != -1:
            mem_available = float(line.split(' ')[1].strip())
            resource_utilization['mem_metrics']['mem_available'] = '%.2f' % (mem_available)
        elif line.find('actual') != -1:
            mem_actual = float(line.split(' ')[1].strip())
    if mem_unused and mem_available and mem_actual:
        mem_buffers = mem_actual - mem_available
        resource_utilization['mem_metrics']['mem_buffers'] = '%.2f' % (mem_buffers)
        resource_utilization['mem_metrics']['mem_rate'] = \
        '%.2f' % ((mem_available - mem_unused - mem_buffers) / mem_available * 100)
    else:
        resource_utilization['mem_metrics']['mem_buffers'] = '%.2f' % (0.00)
        resource_utilization['mem_metrics']['mem_rate'] = '%.2f' % (0.00)
    disks_spec = get_disks_spec(vm)
    for disk_spec in disks_spec:
        disk_metrics = {}
        disk_device = disk_spec[0]
        disk_metrics['device'] = disk_device
        stats1 = {}
        stats2 = {}
        blk_dev_stats1 = runCmdRaiseException('virsh domblkstat --device %s --domain %s' % (disk_device, vm))
        for line in blk_dev_stats1:
            if line.find('rd_req') != -1:
                stats1['rd_req'] = float(line.split(' ')[2].strip())
            elif line.find('rd_bytes') != -1:
                stats1['rd_bytes'] = float(line.split(' ')[2].strip())
            elif line.find('wr_req') != -1:
                stats1['wr_req'] = float(line.split(' ')[2].strip())
            elif line.find('wr_bytes') != -1:
                stats1['wr_bytes'] = float(line.split(' ')[2].strip())
        time.sleep(0.1)
        blk_dev_stats2 = runCmdRaiseException('virsh domblkstat --device %s --domain %s' % (disk_device, vm))
        for line in blk_dev_stats2:
            if line.find('rd_req') != -1:
                stats2['rd_req'] = float(line.split(' ')[2].strip())
            elif line.find('rd_bytes') != -1:
                stats2['rd_bytes'] = float(line.split(' ')[2].strip())
            elif line.find('wr_req') != -1:
                stats2['wr_req'] = float(line.split(' ')[2].strip())
            elif line.find('wr_bytes') != -1:
                stats2['wr_bytes'] = float(line.split(' ')[2].strip())
        disk_metrics['disk_read_requests_per_secend'] = '%.2f' % ((stats2['rd_req'] - stats1['rd_req']) / 0.1) \
        if (stats2['rd_req'] - stats1['rd_req']) > 0 else '%.2f' % (0.00)
        disk_metrics['disk_read_bytes_per_secend'] = '%.2f' % ((stats2['rd_bytes'] - stats1['rd_bytes']) / 0.1) \
        if (stats2['rd_bytes'] - stats1['rd_bytes']) > 0 else '%.2f' % (0.00)
        disk_metrics['disk_write_requests_per_secend'] = '%.2f' % ((stats2['wr_req'] - stats1['wr_req']) / 0.1) \
        if (stats2['wr_req'] - stats1['wr_req']) > 0 else '%.2f' % (0.00)
        disk_metrics['disk_write_bytes_per_secend'] = '%.2f' % ((stats2['wr_bytes'] - stats1['wr_bytes']) / 0.1) \
        if (stats2['wr_bytes'] - stats1['wr_bytes']) > 0 else '%.2f' % (0.00)
        resource_utilization['disks_metrics'].append(disk_metrics)
    macs = get_macs(vm)
    for mac in macs:
        net_metrics = {}
        net_metrics['device'] = mac
        stats1 = {}
        stats2 = {}
        net_dev_stats1 = runCmdRaiseException('virsh domifstat --interface %s --domain %s' % (mac, vm))
        for line in net_dev_stats1:
            if line.find('rx_bytes') != -1:
                stats1['rx_bytes'] = float(line.split(' ')[2].strip())
            elif line.find('rx_packets') != -1:
                stats1['rx_packets'] = float(line.split(' ')[2].strip())
            elif line.find('tx_packets') != -1:
                stats1['tx_packets'] = float(line.split(' ')[2].strip())
            elif line.find('tx_bytes') != -1:
                stats1['tx_bytes'] = float(line.split(' ')[2].strip())
            elif line.find('rx_drop') != -1:
                stats1['rx_drop'] = float(line.split(' ')[2].strip())
            elif line.find('rx_errs') != -1:
                stats1['rx_errs'] = float(line.split(' ')[2].strip())
            elif line.find('tx_errs') != -1:
                stats1['tx_errs'] = float(line.split(' ')[2].strip())
            elif line.find('tx_drop') != -1:
                stats1['tx_drop'] = float(line.split(' ')[2].strip())
        time.sleep(0.1)
        net_dev_stats2 = runCmdRaiseException('virsh domifstat --interface %s --domain %s' % (mac, vm))
        for line in net_dev_stats2:
            if line.find('rx_bytes') != -1:
                stats2['rx_bytes'] = float(line.split(' ')[2].strip())
            elif line.find('rx_packets') != -1:
                stats2['rx_packets'] = float(line.split(' ')[2].strip())
            elif line.find('tx_packets') != -1:
                stats2['tx_packets'] = float(line.split(' ')[2].strip())
            elif line.find('tx_bytes') != -1:
                stats2['tx_bytes'] = float(line.split(' ')[2].strip())
            elif line.find('rx_drop') != -1:
                stats2['rx_drop'] = float(line.split(' ')[2].strip())
            elif line.find('rx_errs') != -1:
                stats2['rx_errs'] = float(line.split(' ')[2].strip())
            elif line.find('tx_errs') != -1:
                stats2['tx_errs'] = float(line.split(' ')[2].strip())
            elif line.find('tx_drop') != -1:
                stats2['tx_drop'] = float(line.split(' ')[2].strip())
        net_metrics['network_read_packages_per_secend'] = '%.2f' % ((stats2['rx_packets'] - stats1['rx_packets']) / 0.1) \
        if (stats2['rx_packets'] - stats1['rx_packets']) > 0 else '%.2f' % (0.00)
        net_metrics['network_read_bytes_per_secend'] = '%.2f' % ((stats2['rx_bytes'] - stats1['rx_bytes']) / 0.1) \
        if (stats2['rx_bytes'] - stats1['rx_bytes']) > 0 else '%.2f' % (0.00)
        net_metrics['network_write_packages_per_secend'] = '%.2f' % ((stats2['tx_packets'] - stats1['tx_packets']) / 0.1) \
        if (stats2['tx_packets'] - stats1['tx_packets']) > 0 else '%.2f' % (0.00)
        net_metrics['network_write_bytes_per_secend'] = '%.2f' % ((stats2['tx_bytes'] - stats1['tx_bytes']) / 0.1) \
        if (stats2['tx_bytes'] - stats1['tx_bytes']) > 0 else '%.2f' % (0.00)
        resource_utilization['networks_metrics'].append(net_metrics)   
        net_metrics['network_read_errors_per_secend'] = '%.2f' % ((stats2['rx_errs'] - stats1['rx_errs']) / 0.1) \
        if (stats2['rx_errs'] - stats1['rx_errs']) > 0 else '%.2f' % (0.00)
        net_metrics['network_read_drops_per_secend'] = '%.2f' % ((stats2['rx_drop'] - stats1['rx_drop']) / 0.1) \
        if (stats2['rx_drop'] - stats1['rx_drop']) > 0 else '%.2f' % (0.00)
        net_metrics['network_write_errors_per_secend'] = '%.2f' % ((stats2['tx_errs'] - stats1['tx_errs']) / 0.1) \
        if (stats2['tx_errs'] - stats1['tx_errs']) > 0 else '%.2f' % (0.00)
        net_metrics['network_write_drops_per_secend'] = '%.2f' % ((stats2['tx_drop'] - stats1['tx_drop']) / 0.1) \
        if (stats2['tx_drop'] - stats1['tx_drop']) > 0 else '%.2f' % (0.00)
        resource_utilization['networks_metrics'].append(net_metrics)   
    #     vm_resource_utilization()
    return resource_utilization

def set_vm_mem_period(vm, sec):
    runCmdRaiseException('virsh dommemstat --period %s --domain %s --config --live' % (str(sec), vm))

def vm_collector_threads(vm):
    while True:
        t = threading.Thread(target=collect_vm_metrics,args=(vm,))
        t.setDaemon(True)
        t.start()
        time.sleep(5)

if __name__ == '__main__':
#     start_http_server(9092)
#     vm_list = list_active_vms()
#     threads = []
#     for url in vm_list:
#         t = threading.Thread(target=vm_collector_threads,args=(url,))
#         threads.append(t)
#     for thread in threads:
#         thread.setDaemon(True)
#         thread.start()
#     thread.join()
    import pprint
    set_vm_mem_period('vm010', 5)
    pprint.pprint(collect_vm_metrics("vm010"))