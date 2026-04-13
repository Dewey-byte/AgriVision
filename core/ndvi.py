import cv2

def compute_exg(frame):
    B, G, R = cv2.split(frame.astype("float"))
    exg = 2 * G - R - B
    return exg