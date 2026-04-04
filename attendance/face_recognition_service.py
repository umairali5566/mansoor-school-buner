try:
    import cv2
except ModuleNotFoundError:  # pragma: no cover - runtime dependency
    cv2 = None

try:
    import face_recognition
except ModuleNotFoundError:  # pragma: no cover - runtime dependency
    face_recognition = None

try:
    import numpy as np
except ModuleNotFoundError:  # pragma: no cover - runtime dependency
    np = None
from datetime import datetime
from django.utils import timezone
from attendance.models import StudentFaceData
from attendance.services import save_attendance_record


def run_auto_attendance():
    if cv2 is None or face_recognition is None or np is None:
        return

    # Time check (9–10 AM only)
    now = datetime.now()
    if not (9 <= now.hour < 10):
        return


    video_capture = cv2.VideoCapture(0)
    if not video_capture.isOpened():
        video_capture.release()
        return

    # Load known faces
    known_encodings = []
    known_students = []

    students = StudentFaceData.objects.select_related("student").all()

    for student_face in students:
        if not student_face.encoding:
            continue
        encoding = np.frombuffer(student_face.encoding, dtype=np.float64)
        if encoding.size == 0:
            continue
        known_encodings.append(encoding)
        known_students.append(student_face.student)

    marked_students = set()

    while True:
        ret, frame = video_capture.read()
        if not ret or frame is None:
            continue
        rgb_frame = frame[:, :, ::-1]

        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        for face_encoding in face_encodings:

            matches = face_recognition.compare_faces(known_encodings, face_encoding)
            face_distances = face_recognition.face_distance(known_encodings, face_encoding)

            if True in matches:
                best_match_index = np.argmin(face_distances)
                student = known_students[best_match_index]

                if student not in marked_students:
                    save_attendance_record(
                        student=student,
                        status="Present",
                        marked_by="FACE",
                        attendance_date=timezone.localdate(),
                        marked_at=timezone.now(),
                        overwrite_existing=True,
                    )
                    # logged attendance for student
                    marked_students.add(student)

        cv2.imshow("Auto Attendance", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video_capture.release()
    try:
        cv2.destroyAllWindows()
    except Exception:
        pass
