import prometheus_client
import re
from prometheus_client import Gauge,start_http_server,Counter
import pycurl
import time
import threading
from io import BytesIO
from utils.utils import runCmdRaiseException
from utils.libvirt_util import list_active_vms

vm_resource_utilization = Gauge('vm_resource_utilization', 'The resource utilization of virtual machine', ['cpu_user_time', 'cpu_system_time', 'cpu_time', 'mem_actual', 'mem_available', 'mem_last_update'])

def collect_vm_metrics(vm):
    resource_utilization = {'cpu_user_time': '', 'cpu_system_time': '', 'cpu_time': '', 'mem_actual': '', 'mem_available': '', 'mem_last_update': ''}
    cpu_stats = runCmdRaiseException('virsh cpu-stats --total %s' % vm)
    for line in cpu_stats:
        if line.find('cpu_time') != -1:
            p1 = r'^(\s*cpu_time\s*)([\S*]+)\s*(\S*)'
            m1 = re.match(p1, line)
            if m1:
                resource_utilization['cpu_time'] = int(m1.group(2))
        elif line.find('system_time') != -1:
            p1 = r'^(\s*system_time\s*)([\S*]+)\s*(\S*)'
            m1 = re.match(p1, line)
            if m1:
                resource_utilization['cpu_system_time'] = int(m1.group(2))
        elif line.find('user_time') != -1:
            p1 = r'^(\s*user_time\s*)([\S*]+)\s*(\S*)'
            m1 = re.match(p1, line)
            if m1:
                resource_utilization['cpu_user_time'] = int(m1.group(2))
    mem_stats = runCmdRaiseException('virsh dommemstat %s' % vm)
    for line in mem_stats:
        if line.find('actual') != -1:
            resource_utilization['mem_actual'] = line.split(' ')[1].strip()
        elif line.find('available') != -1:
            resource_utilization['mem_available'] = line.split(' ')[1].strip()
        elif line.find('last_update') != -1:
            resource_utilization['mem_last_update'] = line.split(' ')[1].strip()
#     vm_resource_utilization()
    return resource_utilization

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
    print(collect_vm_metrics("vm010"))