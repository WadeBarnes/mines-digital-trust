from flask import Flask, jsonify, abort, request, make_response
import time


from app import issuer, logging

def register_routes(app):

    @app.route('/health', methods=['GET'])
    def health_check():
        if issuer.tob_connection_synced():
            return make_response(jsonify({'success': True}), 200)
        else:
            abort(503, "Connection not yet synced")

    @app.route('/readiness', methods=['GET'])
    def readiness_check():
        """
        A readiness probe checks if the container is ready to handle requests.
        A failed readiness probe means that a container should not receive any traffic from a proxy, even if it's running.
        """
        if issuer.tob_connection_synced():
            return make_response(jsonify({'success': True}), 200)
        else:
            abort(503, "Connection not ready to process requests")

    @app.route('/liveness', methods=['GET'])
    def liveness_check():
        """
        A liveness probe checks if the container is still running.
        If the liveness probe fails, the container is killed.
        """
        if issuer.issuer_liveness_check():
            return make_response(jsonify({'success': True}), 200)
        else:
            abort(503, "Connection is not live")

    @app.route('/status/reset', methods=['GET'])
    def clear_status():
        logging.clear_stats()
        return make_response(jsonify({'success': True}), 200)

    @app.route('/status', methods=['GET'])
    def get_status():
        return make_response(jsonify(logging.get_stats()), 200)

    @app.errorhandler(404)
    def not_found(error):
        return make_response(jsonify({'error': 'Not found'}), 404)

    @app.route('/issue-credential', methods=['POST'])
    def submit_credential():
        """
        Exposed method to proxy credential issuance requests.
        """
        if not issuer.tob_connection_synced():
            abort(503, "Connection not yet synced")

        start_time = time.perf_counter()
        method = 'submit_credential.batch'

        if not request.json:
            end_time = time.perf_counter()
            issuer.log_timing_method(method, start_time, end_time, False)
            abort(400)

        cred_input = request.json

        response = issuer.handle_send_credential(cred_input)

        end_time = time.perf_counter()
        logging.log_timing_method(method, start_time, end_time, True)

        return response

    @app.route('/api/agentcb/topic/<topic>/', methods=['POST'])
    def agent_callback(topic):
        """
        Main callback for aries agent.  Dispatches calls based on the supplied topic.
        """
        start_time = time.perf_counter()
        method = 'agent_callback.' + topic

        if not request.json:
            end_time = time.perf_counter()
            issuer.log_timing_method(method, start_time, end_time, False)
            abort(400)

        message = request.json
        logging.log_timing_event(method, message, start_time, None, False)

        # dispatch based on the topic type
        if topic == issuer.TOPIC_CONNECTIONS:
            if "state" in message:
                method = method + '.' + message["state"]
                response = issuer.handle_connections(message["state"], message)
            else:
                response = jsonify({})

        elif topic == issuer.TOPIC_CONNECTIONS_ACTIVITY:
            response = jsonify({})

        elif topic == issuer.TOPIC_CREDENTIALS:
            if "state" in message:
                method = method + '.' + message["state"]
                response = issuer.handle_credentials(message["state"], message)
            else:
                response = jsonify({})

        elif topic == issuer.TOPIC_PRESENTATIONS:
            if "state" in message:
                method = method + '.' + message["state"]
                response = issuer.handle_presentations(message["state"], message)
            else:
                response = jsonify({})

        elif topic == issuer.TOPIC_GET_ACTIVE_MENU:
            response = issuer.handle_get_active_menu(message)

        elif topic == issuer.TOPIC_PERFORM_MENU_ACTION:
            response = issuer.handle_perform_menu_action(message)

        elif topic == issuer.TOPIC_ISSUER_REGISTRATION:
            response = issuer.handle_register_issuer(message)
        
        elif topic == issuer.TOPIC_PROBLEM_REPORT:
            response = issuer.handle_problem_report(message)

        else:
            print("Callback: topic=", topic, ", message=", message)
            end_time = time.perf_counter()
            logging.log_timing_method(method, start_time, end_time, False)
            logging.log_timing_event(method, message, start_time, end_time, False)
            abort(400, {'message': 'Invalid topic: ' + topic})

        end_time = time.perf_counter()
        logging.log_timing_method(method, start_time, end_time, True)
        logging.log_timing_event(method, message, start_time, end_time, True)

        return response
