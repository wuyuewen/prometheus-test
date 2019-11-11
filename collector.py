import prometheus_client
import re
from prometheus_client import Gauge,start_http_server,Counter
import pycurl
import time
import threading
from io import BytesIO
from utils.utils import runCmdRaiseException
from utils.libvirt_util import list_active_vms, get_disks_spec

vm_resource_utilization = Gauge('vm_resource_utilization', 'The resource utilization of virtual machine', \
                                ['cpu_metrics', 'mem_metrics', 'disks_metrics', 'networks_metrics'])

def collect_vm_metrics(vm):
    resource_utilization = {'cpu_metrics': {}, 'mem_metrics': {},
                            'disks_metrics': [], 'networks_metrics': []}
    cpu_stats = runCmdRaiseException('virsh cpu-stats --total %s' % vm)
    for line in cpu_stats:
        if line.find('cpu_time') != -1:
            p1 = r'^(\s*cpu_time\s*)([\S*]+)\s*(\S*)'
            m1 = re.match(p1, line)
            if m1:
                resource_utilization['cpu_metrics']['cpu_time'] = float(m1.group(2))
        elif line.find('system_time') != -1:
            p1 = r'^(\s*system_time\s*)([\S*]+)\s*(\S*)'
            m1 = re.match(p1, line)
            if m1:
                resource_utilization['cpu_metrics']['cpu_system_time'] = float(m1.group(2))
        elif line.find('user_time') != -1:
            p1 = r'^(\s*user_time\s*)([\S*]+)\s*(\S*)'
            m1 = re.match(p1, line)
            if m1:
                resource_utilization['cpu_metrics']['cpu_user_time'] = float(m1.group(2))
    if resource_utilization['cpu_metrics']['cpu_user_time'] and resource_utilization['cpu_metrics']['cpu_system_time'] \
    and resource_utilization['cpu_metrics']['cpu_time']:
        resource_utilization['cpu_metrics']['cpu_rate'] = \
        (resource_utilization['cpu_metrics']['cpu_user_time'] + resource_utilization['cpu_metrics']['cpu_system_time']) \
        / resource_utilization['cpu_metrics']['cpu_time'] * 100
    else:
        resource_utilization['cpu_metrics']['cpu_rate'] = 0
    mem_stats = runCmdRaiseException('virsh dommemstat %s' % vm)
    for line in mem_stats:
        if line.find('actual') != -1:
            resource_utilization['mem_metrics']['mem_actual'] = int(line.split(' ')[1].strip())
        elif line.find('available') != -1:
            resource_utilization['mem_metrics']['mem_available'] = int(line.split(' ')[1].strip())
        elif line.find('last_update') != -1:
            resource_utilization['mem_metrics']['mem_last_update'] = int(line.split(' ')[1].strip())
    if resource_utilization['mem_metrics']['mem_available'] and resource_utilization['mem_metrics']['mem_actual']:
        resource_utilization['mem_metrics']['mem_rate'] = (resource_utilization['mem_metrics']['mem_actual'] \
        - resource_utilization['mem_metrics']['mem_available']) / resource_utilization['mem_metrics']['mem_actual'] * 100
    else:
        resource_utilization['mem_metrics']['mem_rate'] = 0
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
                stats1['rd_req'] = int(line.split(' ')[2].strip())
            elif line.find('rd_bytes') != -1:
                stats1['rd_bytes'] = int(line.split(' ')[2].strip())
            elif line.find('wr_req') != -1:
                stats1['wr_req'] = int(line.split(' ')[2].strip())
            elif line.find('wr_bytes') != -1:
                stats1['wr_bytes'] = int(line.split(' ')[2].strip())
        time.sleep(0.1)
        blk_dev_stats2 = runCmdRaiseException('virsh domblkstat --device %s --domain %s' % (disk_device, vm))
        for line in blk_dev_stats2:
            if line.find('rd_req') != -1:
                stats2['rd_req'] = int(line.split(' ')[2].strip())
            elif line.find('rd_bytes') != -1:
                stats2['rd_bytes'] = int(line.split(' ')[2].strip())
            elif line.find('wr_req') != -1:
                stats2['wr_req'] = int(line.split(' ')[2].strip())
            elif line.find('wr_bytes') != -1:
                stats2['wr_bytes'] = int(line.split(' ')[2].strip())
        disk_metrics['disk_read_requests_per_secend'] = (stats2['rd_req'] - stats1['rd_req']) / 0.1 \
        if (stats2['rd_req'] - stats1['rd_req']) >= 0 else 0
        disk_metrics['disk_read_bytes_per_secend'] = (stats2['rd_bytes'] - stats1['rd_bytes']) / 0.1 \
        if (stats2['rd_bytes'] - stats1['rd_bytes']) >= 0 else 0
        disk_metrics['disk_write_requests_per_secend'] = (stats2['wr_req'] - stats1['wr_req']) / 0.1 \
        if (stats2['wr_req'] - stats1['wr_req']) >= 0 else 0
        disk_metrics['disk_write_bytes_per_secend'] = (stats2['wr_bytes'] - stats1['wr_bytes']) / 0.1 \
        if (stats2['wr_bytes'] - stats1['wr_bytes']) >= 0 else 0
        resource_utilization['disks_metrics'].append(disk_metrics)
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