import face_recognition
import cv2
import numpy as np
from accounts.models import Student
from attendance.models import StudentFaceData

def recognize_face_from_camera():

    video_capture = cv2.VideoCapture(0)

    known_encodings = []
    known_students = []

    # Load all saved encodings
    students_faces = StudentFaceData.objects.all()

    for face in students_faces:
        if face.encoding:
            encoding = np.frombuffer(face.encoding, dtype=np.float64)
            known_encodings.append(encoding)
            known_students.append(face.student)

    detected_student = None

    while True:
        ret, frame = video_capture.read()

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(known_encodings, face_encoding)
            face_distances = face_recognition.face_distance(known_encodings, face_encoding)

            if len(face_distances) > 0:
                best_match_index = np.argmin(face_distances)

                if matches[best_match_index]:
                    detected_student = known_students[best_match_index]
                    break

        cv2.imshow("Camera - Press Q to exit", frame)

        if detected_student is not None:
            break

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

    video_capture.release()
    cv2.destroyAllWindows()

    return detected_student