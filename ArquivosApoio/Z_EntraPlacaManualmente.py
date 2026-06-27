from visionlib.dblib import gravar_movimento
from datetime import datetime

movimentotest1 = {"data": {"log_id": 436375,"occurrence": "Lpr",
    "analytic_id": "1798","region_dic": {"region0": [
        [ 0.346875, 0.36574074074074076 ],
        [ 0.25, 1 ],
        [ 0.7671875, 1 ],
        [ 0.765625, 0.37037037037037035 ]
      ]
    }, "bbox_lst": "null",
    "video_stream": "/media/164",
    "camera_id": 164,
    "camera_name": "6003 veraneio lpr SAIDA",
    "rtsp": "rtsp://admin:31fe72de@cc210e9c7f32.sn.mynetname.net:255/cam/realmonitor?channel=9&subtype=0",
    "address": "Rua Brigadeiro Tobias, 200",
    "description": "null",
    "coordinate": "{\"latitude\":\"\",\"longitude\":\"\"}",
    "created_at": "29/04/2026 12:32:17",
    "rule": "null",
    "plate_value": "NYF5257",
    "car_color": "brown",
    "car_color_confs": 0.777,
    "detections": [
      {
        "plate_value": "NYF5257",
        "car_color": "brown",
        "car_color_confs": 0.777,
        "lpr_linked_groups": [
          {
            "group_id": 3,
            "group_name": "Placas Gerais",
            "group_tag": "PG",
            "alert_when_not_in_target": "true",
            "is_target_complement": "false",
            "kind_trigger": "out_group"
          }
        ],
        "front_plate_kind_trigger": {
          "plate_groups_matched": "true",
          "plate_recurrence": "false",
          "plate_first_occurrence": "false"
        }
      }
    ],
    "image_base64": "foto"
  },
  "app": {}
}


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
print(f"prestador: {dadosdic.get('placa','NA')} - IdCamera: {dadosdic.get('camera_id','NA')} - {datetime.now()}")


# dadosdic = gravar_movimento(movimentotest2)
# print(f"Processado sem vaga disponível: {dadosdic.get('placa','NA')} - IdCamera: {dadosdic.get('camera_id','NA')} - {datetime.now()}")

# dadosdic = gravar_movimento(movimentotest3)
# print(f"Processado sem permissão: {dadosdic.get('placa','NA')} - IdCamera: {dadosdic.get('camera_id','NA')} - {datetime.now()}")