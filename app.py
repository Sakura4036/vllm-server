from flask import Flask, request, Response, jsonify
from flask_restx import Api, Resource, fields
from instance_manager import InstanceManager
import threading
import time
from router import proxy_openai_request
import os

# 创建 Flask 应用和 Flask-RESTx API
app = Flask(__name__)
api = Api(app, title='vLLM Instance Manager', version='1.0', description='Manage and deploy multiple vLLM model instances')

# 初始化实例管理器
instance_manager = InstanceManager()

# 定义用于序列化实例信息的模型
instance_model = api.model('Instance', {
    'model_name': fields.String(required=True, description='Model name'),
    'port': fields.Integer(required=True, description='Port number'),
    'status': fields.String(required=True, description='Instance status'),
    'last_active': fields.Float(required=True, description='Last active timestamp'),
    'timeout': fields.Integer(required=True, description='Timeout in seconds')
})

# 定义用于创建实例的请求体模型
create_instance_model = api.model('CreateInstance', {
    'model_name': fields.String(required=True, description='Model name'),
    'timeout': fields.Integer(required=False, description='Timeout in seconds', default=600)
})

@api.route('/instances')
class InstanceList(Resource):
    @api.marshal_with(instance_model, as_list=True)
    def get(self):
        """
        Get all active vllm instances.
        """
        return list(instance_manager.list_instances().values())

    @api.expect(create_instance_model)
    def post(self):
        """
        Create and start a new vllm instance.
        """
        data = request.json
        model_name = data.get('model_name')
        timeout = data.get('timeout', 600)
        if not model_name:
            return {'message': 'model_name is required'}, 400
        try:
            instance_id = instance_manager.create_instance(model_name, timeout)
            instance = instance_manager.get_instance(instance_id)
            return {
                'instance_id': instance_id,
                'model_name': instance.model_name,
                'port': instance.port,
                'status': instance.status,
                'last_active': instance.last_active,
                'timeout': instance.timeout
            }, 201
        except Exception as e:
            return {'message': str(e)}, 500

@api.route('/instances/<string:instance_id>')
class Instance(Resource):
    def delete(self, instance_id):
        """
        Delete (stop) a vllm instance by its ID.
        """
        instance = instance_manager.get_instance(instance_id)
        if not instance:
            return {'message': 'Instance not found'}, 404
        instance_manager.delete_instance(instance_id)
        return {'message': f'Instance {instance_id} deleted.'}, 200

@api.route('/v1/chat/completions')
class ChatCompletions(Resource):
    def post(self):
        """
        Proxy /v1/chat/completions request to the correct vllm instance.
        """
        result = proxy_openai_request(
            instance_manager,
            path='/v1/chat/completions',
            request_method='POST',
            request_data=request.json,
            request_headers=request.headers
        )
        # 处理流式响应
        if isinstance(result, tuple) and callable(result[0]):
            generator, status, headers = result
            return Response(generator(), status=status, headers=dict(headers), content_type='application/json')
        # 非流式响应
        if isinstance(result, tuple):
            content, status, headers = result
            return Response(content, status=status, headers=dict(headers), content_type='application/json')
        # 错误响应
        return result

@api.route('/v1/completions')
class Completions(Resource):
    def post(self):
        """
        Proxy /v1/completions request to the correct vllm instance.
        """
        result = proxy_openai_request(
            instance_manager,
            path='/v1/completions',
            request_method='POST',
            request_data=request.json,
            request_headers=request.headers
        )
        # 处理流式响应
        if isinstance(result, tuple) and callable(result[0]):
            generator, status, headers = result
            return Response(generator(), status=status, headers=dict(headers), content_type='application/json')
        # 非流式响应
        if isinstance(result, tuple):
            content, status, headers = result
            return Response(content, status=status, headers=dict(headers), content_type='application/json')
        # 错误响应
        return result

@api.route('/v1/models')
class Models(Resource):
    def get(self):
        """
        Return all active vllm models in OpenAI-compatible format.
        """
        # 聚合所有激活实例的模型信息
        instances = instance_manager.list_instances()
        data = []
        for iid, inst in instances.items():
            data.append({
                'id': inst['model_name'],
                'object': 'model',
                'instance_id': iid,
                'status': inst['status'],
                'port': inst['port'],
                'last_active': inst['last_active'],
                'timeout': inst['timeout']
            })
        return {'object': 'list', 'data': data}, 200

@app.route('/health')
def health_check():
    """
    Health check endpoint. Returns basic service and instance manager status.
    """
    try:
        # 检查 Flask、实例管理器、子进程数量
        instances = instance_manager.list_instances()
        process_count = len(os.popen('ps -ef | grep vllm.entrypoints.openai.api_server | grep -v grep').readlines())
        return jsonify({
            'status': 'ok',
            'instance_count': len(instances),
            'vllm_process_count': process_count
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.errorhandler(Exception)
def handle_exception(e):
    """
    Global error handler. Returns all errors in unified JSON format.
    """
    import traceback
    return jsonify({
        'status': 'error',
        'message': str(e),
        'trace': traceback.format_exc()
    }), 500

# 后台线程：定时清理失活实例
def cleanup_expired_instances():
    """
    Background thread to periodically clean up expired vllm instances.
    """
    while True:
        instance_manager.cleanup_expired()
        time.sleep(30)  # 每 30 秒检查一次

def start_cleanup_thread():
    """
    Start the background cleanup thread.
    """
    thread = threading.Thread(target=cleanup_expired_instances, daemon=True)
    thread.start()

# 启动后台线程
def main():
    start_cleanup_thread()
    app.run(host='0.0.0.0', port=5000, debug=True)

if __name__ == '__main__':
    main() 