try:
    import face_recognition
except ModuleNotFoundError:  # pragma: no cover - runtime dependency
    face_recognition = None

try:
    import cv2
except ModuleNotFoundError:  # pragma: no cover - runtime dependency
    cv2 = None

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - runtime dependency
    np = None

from attendance.models import StudentFaceData


def recognize_face_from_camera():
    if cv2 is None or face_recognition is None or np is None:
        return None

    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened():
        video_capture.release()
        return None

    known_encodings = []
    known_students = []

    for face in StudentFaceData.objects.select_related("student").all():
        if not face.encoding:
            continue
        encoding = np.frombuffer(face.encoding, dtype=np.float64)
        if encoding.size == 0:
            continue
        known_encodings.append(encoding)
        known_students.append(face.student)

    if not known_encodings:
        video_capture.release()
        return None

    detected_student = None
    failed_reads = 0

    try:
        while True:
            ret, frame = video_capture.read()
            if not ret or frame is None:
                failed_reads += 1
                if failed_reads >= 20:
                    break
                continue

            rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            face_locations = face_recognition.face_locations(rgb_frame)
            face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

            for face_encoding in face_encodings:
                matches = face_recognition.compare_faces(known_encodings, face_encoding)
                face_distances = face_recognition.face_distance(known_encodings, face_encoding)

                if len(face_distances) > 0:
                    best_match_index = int(np.argmin(face_distances))
                    if matches[best_match_index]:
                        detected_student = known_students[best_match_index]
                        break

            cv2.imshow("Camera - Press Q to exit", frame)

            if detected_student is not None:
                break

            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        video_capture.release()
        try:
            cv2.destroyAllWindows()
        except Exception:
            pass

    return detected_student
