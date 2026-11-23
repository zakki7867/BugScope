class ThreadSafeCounter:
    def __init__(self):
        self.count = 0

    def increment(self, step=1):
        curr = self.count
        self.count = curr + step
        return self.count
