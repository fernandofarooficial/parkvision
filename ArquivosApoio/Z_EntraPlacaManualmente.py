from visionlib.dblib import gravar_movimento
from datetime import datetime

movimentotest1 =  {'data': {'log_id': 99999, 'occurrence': 'Lpr',
                           'analytic_id': '929',
                           'region_dic': {'region0': [[1,1], [1,1], [1,1], [1,1], [1,1]]},
                           'bbox_lst': None, 'video_stream': 'm', 'camera_id': 75,
                           'camera_name': '6003 E', 'rtsp': 'rtsp:m',
                           'address': 'Veraneio Entrada', 'description': None,
                           'coordinate': '{"latitude":"","longitude":""}',
                           'created_at': '07/04/2026 15:00:00', 'rule': None,
                           'plate_value': 'USA1B99', 'car_color': 'white', 'car_color_confs': 0.91,
                           'image_base64': '/9j/4AAQSkZJRgABAQAAAQ'}}


movimentotest2 =  {'data': {'log_id': 88888, 'occurrence': 'Lpr',
                           'analytic_id': '929',
                           'region_dic': {'region0': [[1,1], [1,1], [1,1], [1,1], [1,1]]},
                           'bbox_lst': None, 'video_stream': 'm', 'camera_id': 75,
                           'camera_name': '6003 E', 'rtsp': 'rtsp:m',
                           'address': 'Veraneio Entrada', 'description': None,
                           'coordinate': '{"latitude":"","longitude":""}',
                           'created_at': '07/04/2026 15:03:15', 'rule': None,
                           'plate_value': 'FHZ1I06', 'car_color': 'white', 'car_color_confs': 0.91,
                           'image_base64': '/9j/4AAQSkZJRgABAQAAAQ'}}

movimentotest3 =  {'data': {'log_id': 77777, 'occurrence': 'Lpr',
                           'analytic_id': '929',
                           'region_dic': {'region0': [[1,1], [1,1], [1,1], [1,1], [1,1]]},
                           'bbox_lst': None, 'video_stream': 'm', 'camera_id': 75,
                           'camera_name': '6003 E', 'rtsp': 'rtsp:m',
                           'address': 'Veraneio Entrada', 'description': None,
                           'coordinate': '{"latitude":"","longitude":""}',
                           'created_at': '07/04/2026 15:05:30', 'rule': None,
                           'plate_value': 'TEG9F15', 'car_color': 'white', 'car_color_confs': 0.91,
                           'image_base64': '/9j/4AAQSkZJRgABAQAAAQ'}}

dadosdic = gravar_movimento(movimentotest1)
print(f"Processado placa sem cadastro: {dadosdic.get('placa','NA')} - IdCamera: {dadosdic.get('camera_id','NA')} - {datetime.now()}")

dadosdic = gravar_movimento(movimentotest2)
print(f"Processado sem vaga disponível: {dadosdic.get('placa','NA')} - IdCamera: {dadosdic.get('camera_id','NA')} - {datetime.now()}")

dadosdic = gravar_movimento(movimentotest3)
print(f"Processado sem permissão: {dadosdic.get('placa','NA')} - IdCamera: {dadosdic.get('camera_id','NA')} - {datetime.now()}")