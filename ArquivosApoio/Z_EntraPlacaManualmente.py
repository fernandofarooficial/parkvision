from db_lib_generico import gravar_movimento
from datetime import datetime

movimentotest1 =  {'data': {'log_id': 99999, 'occurrence': 'Lpr',
                           'analytic_id': '929',
                           'region_dic': {'region0': [[1,1], [1,1], [1,1], [1,1], [1,1]]},
                           'bbox_lst': None, 'video_stream': 'm', 'camera_id': 89,
                           'camera_name': '6004 E', 'rtsp': 'rtsp:m',
                           'address': 'BLAIA TESTE', 'description': None,
                           'coordinate': '{"latitude":"","longitude":""}',
                           'created_at': '08/07/2025 15:25:39', 'rule': None,
                           'plate_value': 'USA1B99', 'car_color': 'white', 'car_color_confs': 0.91,
                           'image_base64': '/9j/4AAQSkZJRgABAQAAAQ'}}


movimentotest2 =  {'data': {'log_id': 12345, 'occurrence': 'Lpr',
                           'analytic_id': '124',
                           'region_dic': {'region0': [[1,1], [1,1], [1,1], [1,1], [1,1]]},
                           'bbox_lst': None, 'video_stream': 'm', 'camera_id': 199,
                           'camera_name': '1234 TESTE APP VISIT ENTRADA', 'rtsp': 'rtsp:m',
                           'address': 'UIRAPURUS', 'description': None,
                           'coordinate': '{"latitude":"","longitude":""}',
                           'created_at': '30/10/2025 17:30:10', 'rule': None,
                           'plate_value': 'JBH5ED0', 'car_color': 'white', 'car_color_confs': 0.91,
                           'image_base64': '/9j/4AAQSkZJRgABAQAAAQ'}}

'''
dadosdic = gravar_movimento(movimentotest1)
print(f"Placa: {dadosdic.get('placa','NA')} - IdCamera: {dadosdic.get('camera_id','NA')}")
print(datetime.now())
'''

dadosdic = gravar_movimento(movimentotest2)
print(f"Placa: {dadosdic.get('placa','NA')} - IdCamera: {dadosdic.get('camera_id','NA')}")
print(datetime.now())
