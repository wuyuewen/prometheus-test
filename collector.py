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
            m1 = re.match(line, p1)
            if m1:
                resource_utilization['cpu_time'] = m1.group(1)
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