"""Single-slot camera reader: old frames are overwritten, never queued."""
import threading
import time
import cv2

class LatestCapture:
    def __init__(self,source):
        self.capture = cv2.VideoCapture(source)
        if not self.capture.isOpened(): raise RuntimeError(f"Cannot open camera: {source}")
        self.capture.set(cv2.CAP_PROP_BUFFERSIZE,1)  # Backend may ignore this request.
        self.condition = threading.Condition(); self.packet=None; self.sequence=0
        self.stopped=False; self.failed=False
        self.thread=threading.Thread(target=self._read,daemon=True); self.thread.start()

    def _read(self):
        while not self.stopped:
            ok,image = self.capture.read()
            with self.condition:
                if not ok:
                    self.failed=True; self.condition.notify_all(); break
                self.sequence+=1
                self.packet=(self.sequence,time.monotonic(),image)
                self.condition.notify_all()

    def get(self,after,timeout=.25):
        with self.condition:
            self.condition.wait_for(lambda:self.sequence>after or self.failed or self.stopped,timeout)
            return self.packet if self.sequence>after else None

    def close(self):
        self.stopped=True
        with self.condition: self.condition.notify_all()
        self.thread.join(timeout=1)
        # Do not race release against a backend still blocked in read().
        if not self.thread.is_alive(): self.capture.release()
