import socketio
import eventlet

from colorama import Fore, Style
import json

import sandbox
import utils

settings, problems = utils.load_data()

sio = socketio.Server()
static_files = {
    '/': {'content_type': 'text/html', 'filename': './static/index.html'},
    '/assets/img/pulse.svg': {'content_type': 'image/svg+xml', 'filename': './static/assets/img/pulse.svg'},
    '/': './static/'
}

app = socketio.WSGIApp(sio, static_files=static_files)

@sio.on('connect')
def connect(sid, environ):
    sio.emit('problems', [p['name'] for p in problems], room=sid)

@sio.on('heartbeat')
def run(sid):
    return sio.emit("heartbeat", room=sid)

@sio.on('run')
def run(sid, data):
    code = data['code']
    lang = data['lang']
    stdin = data['stdin']
    problem = data['problem']

    if not code or not lang:
        return sio.emit('err', '[ERROR] No code or language submitted!', room=sid)

    if lang not in sandbox.langs.keys():
        return sio.emit('err', '[ERROR] Invalid language.', room=sid)

    if problem:
        problem = [p for p in problems if p['name'] == problem][0]
        if not problem:
            return sio.emit('err', '[ERROR] Invalid task.', room=sid)

    executor = sandbox.langs[lang]
    
    if not problem:
        def output(result):
            if result['stderr']:
                if result['type'] == 'compile':
                    sio.emit('err', f'{Fore.RED}[ERROR] There was an error compiling your code.\n\n', room=sid)
                else:
                    sio.emit('err', f'{Fore.RED}[ERROR] There was an error running your code.\n\n', room=sid)
                sio.emit('err', f"{Fore.RED}{result['stderr'].decode()}", room=sid)

            if result['type'] == 'compile':
                return

            sio.emit('out', f"{Fore.WHITE}{result['stdout'].decode()}", room=sid)

            if result['exit_code'] == 0:
                sio.emit('out', f"{Fore.WHITE}\n-------------------------\n\nThe program executed successfully.\nDuration: {result['duration']}s\n\n\n", room=sid)
            else:
                sio.emit('err', f"{Fore.RED}\n-------------------------\n\nThe program failed to run.\nDuration: {result['duration']}s\nTimeout: {result['timeout']}\nOut of Memory: {result['oom_killed']}\n\n\n", room=sid)

        executor(code, [stdin], output)
    else:
        test_cases = [p['stdin'] for p in problem['tests']]
        test_check = [p['stdout'] for p in problem['tests']]

        passed = True
        failed = 0
        i = 0

        def check(result):
            if result['type'] != 'run':
                return

            nonlocal passed
            nonlocal failed
            nonlocal i

            if utils.check_testcase(result['stdout'].decode(), test_check[i]):
                sio.emit('out', f'{Fore.WHITE}[Task] Passed test case {i + 1} / {len(test_cases)}.\n', room=sid)
            else:
                sio.emit('err', f'{Fore.RED}[Task] Failed test case {i + 1} / {len(test_cases)}.\n', room=sid)
                failed += 1
                passed = False

            i += 1

            if i == len(test_cases):
                end()

        def end():
            if passed:
                sio.emit('out', f"{Fore.BLUE}\nNice job! You passed the task. Here's your flag:\n{Style.BRIGHT}{problem['flag']}", room=sid)
            else:
                sio.emit('err', f"{Fore.RED}\nTask {Style.BRIGHT}{problem['name']}{Style.NORMAL} failed.\n{failed} / {len(test_cases)} test cases failed.", room=sid)

        executor(code, test_cases, check)

if __name__ == '__main__':
    print(f"CodeExec running on 0.0.0.0:{settings['PORT']}...")
    #sio.run(app, host='0.0.0.0', port=settings['PORT'])
    eventlet.wsgi.server(eventlet.listen(('', settings['PORT'])), app)