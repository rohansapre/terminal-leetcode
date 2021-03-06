from threading import Lock

class QuizItem(object):
    def __init__(self, data):
        self.id = int(data['id'])
        self.title = data['title']
        self.url = data['url']
        self.acceptance = data['acceptance']
        self.difficulty = data['difficulty']
        self.lock = data['lock']
        self.pass_status = data['pass']#'None', 'ac', 'notac'
        self.sample_code = None


class EasyLock(object):
    def __init__(self):
        self.lock = Lock()

    def __enter__(self):
        self.lock.acquire()
        return self.lock

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.lock.release()
