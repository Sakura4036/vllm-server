import os
import threading
import time
from argparse import ArgumentParser
from flask import Flask, request, Response, jsonify
from flask_restx import Api, Resource, fields, reqparse
from instance_manager import InstanceManager
from router import proxy_openai_request

# Create Flask app and Flask-RESTx API
app = Flask(__name__)
api = Api(
    app, 
    title='vLLM Instance Manager', 
    version='1.0', 
    description='Manage and deploy multiple vLLM model instances',
    doc='/docs',  # 设置文档路径为 /docs
    default='vLLM API',  # 设置默认命名空间
    default_label='vLLM API endpoints'  # 设置默认标签
)

# Initialize instance manager
instance_manager = InstanceManager()

# Define model for serializing instance info
instance_model = api.model('Instance', {
    'model_name': fields.String(required=True, description='Model name'),
    'port': fields.Integer(required=True, description='Port number'),
    'status': fields.String(required=True, description='Instance status'),
    'last_active': fields.Float(required=True, description='Last active timestamp'),
    'timeout': fields.Integer(required=True, description='Timeout in seconds')
})


create_instance_parser = reqparse.RequestParser()
create_instance_parser.add_argument('model_name', type=str, required=True, help='model name')
create_instance_parser.add_argument('timeout', type=int, required=False, default=600, help='timeout(secend)')


@api.route('/instances')
class InstanceList(Resource):
    @api.doc("get vllm model instances")
    @api.marshal_with(instance_model, as_list=True)
    def get(self):
        """
        Get all active vllm instances.
        """
        return list(instance_manager.list_instances().values())

    @api.doc()
    @api.expect(create_instance_parser)
    @api.marshal_with(instance_model)
    def post(self):
        """
        Create and start a new vllm instance.
        """
        args = create_instance_parser.parse_args()
        model_name = args.get('model_name')
        timeout = args.get('timeout', 600)
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
        # Handle streaming response
        if isinstance(result, tuple) and callable(result[0]):
            generator, status, headers = result
            return Response(generator(), status=status, headers=dict(headers), content_type='application/json')
        # Non-streaming response
        if isinstance(result, tuple):
            content, status, headers = result
            return Response(content, status=status, headers=dict(headers), content_type='application/json')
        # Error response
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
        # Handle streaming response
        if isinstance(result, tuple) and callable(result[0]):
            generator, status, headers = result
            return Response(generator(), status=status, headers=dict(headers), content_type='application/json')
        # Non-streaming response
        if isinstance(result, tuple):
            content, status, headers = result
            return Response(content, status=status, headers=dict(headers), content_type='application/json')
        # Error response
        return result


@api.route('/v1/models')
class Models(Resource):
    def get(self):
        """
        Return all active vllm models in OpenAI-compatible format.
        """
        # Aggregate model info from all active instances
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
        # Check Flask, instance manager, and subprocess count
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


# Background thread: periodically clean up expired instances
def cleanup_expired_instances():
    """
    Background thread to periodically clean up expired vllm instances.
    """
    while True:
        instance_manager.cleanup_expired()
        time.sleep(30)  # Check every 30 seconds


def start_cleanup_thread():
    """
    Start the background cleanup thread.
    """
    thread = threading.Thread(target=cleanup_expired_instances, daemon=True)
    thread.start()


# Start background thread
def main():
    argparse = ArgumentParser()
    argparse.add_argument("--host", type=str, default="0.0.0.0")
    argparse.add_argument("--port", type=int, default=9001)
    argparse.add_argument("--debug", type=bool, default=True)
    args = argparse.parse_args()
    start_cleanup_thread()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == '__main__':
    main()
