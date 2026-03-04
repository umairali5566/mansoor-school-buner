import cv2
import face_recognition
import numpy as np
from datetime import date, datetime
from accounts.models import Student
from attendance.models import Attendance, StudentFaceData


def run_auto_attendance():

    # Time check (9–10 AM only)
    now = datetime.now()
    if not (9 <= now.hour < 10):
        print("Not within attendance time (9-10 AM)")
        return

    print("Starting Face Recognition Attendance...")

    video_capture = cv2.VideoCapture(0)

    # Load known faces
    known_encodings = []
    known_students = []

    students = StudentFaceData.objects.all()

    for student_face in students:
        encoding = np.frombuffer(student_face.encoding)
        known_encodings.append(encoding)
        known_students.append(student_face.student)

    marked_students = set()

    while True:
        ret, frame = video_capture.read()
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
                    Attendance.objects.get_or_create(
                        student=student,
                        date=date.today(),
                        defaults={"status": "Present"}
                    )
                    print(f"Marked Present: {student.user.username}")
                    marked_students.add(student)

        cv2.imshow("Auto Attendance", frame)

        if cv2.waitKey(1) & 0xFF == ord("q"):
            break

    video_capture.release()
    cv2.destroyAllWindows()