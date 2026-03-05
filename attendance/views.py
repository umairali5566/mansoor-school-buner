#import cv2
import pickle
import numpy as np
#import face_recognition
import os
import uuid
from django.conf import settings
from .models import UnknownFace

from collections import deque

# Live recognition messages
LIVE_MESSAGES = deque(maxlen=10)

from django.http import JsonResponse

def live_messages(request):
    return JsonResponse({"messages": list(LIVE_MESSAGES)})

from datetime import date
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.admin.views.decorators import staff_member_required
from django.contrib import messages
from django.http import StreamingHttpResponse
from django.utils.timezone import now
from django.contrib.auth import get_user_model
from django.db.models import Count

from .models import Attendance, StudentFaceData, ClassroomCamera
from .forms import FaceUploadForm
from accounts.models import Student

User = get_user_model()

# =====================================================
# 📸 Upload Face Encoding
# =====================================================

@login_required
def upload_face(request, student_id):
    student = get_object_or_404(Student, id=student_id)

    if request.method == "POST":
        form = FaceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image_file = form.cleaned_data["image"]
            image = face_recognition.load_image_file(image_file)
            encodings = face_recognition.face_encodings(image)

            if encodings:
                encoding = encodings[0]
                face_data, created = StudentFaceData.objects.get_or_create(student=student)
                face_data.encoding = pickle.dumps(encoding)
                face_data.save()
                return redirect("admin_dashboard")
            else:
                form.add_error(None, "No face detected!")

    else:
        form = FaceUploadForm()

    return render(request, "attendance/upload_face.html", {
        "form": form,
        "student": student
    })


# =====================================================
# ✅ Manual Attendance
# =====================================================

@login_required
def mark_attendance(request):
    students = Student.objects.all()

    if request.method == "POST":
        selected_students = request.POST.getlist("students")

        for student_id in selected_students:
            try:
                student = Student.objects.get(id=student_id)
                Attendance.objects.get_or_create(
                    student=student,
                    date=date.today(),
                    defaults={"status": "Present"}
                )
            except Student.DoesNotExist:
                continue

        return redirect("mark_attendance")

    return render(request, "attendance/mark_attendance.html", {
        "students": students
    })


# =====================================================
# 📊 Attendance Report
# =====================================================

def attendance_report(request):

    selected_date = request.GET.get("date")
    selected_class = request.GET.get("class")

    if selected_date:
        records = Attendance.objects.filter(date=selected_date)
    else:
        selected_date = date.today()
        records = Attendance.objects.filter(date=selected_date)

    if selected_class:
        records = records.filter(student__class_name=selected_class)

    present_count = records.filter(status="Present").count()
    absent_count = records.filter(status="Absent").count()

    classes = Student.objects.values_list("class_name", flat=True).distinct()

    return render(request, "attendance/attendance_report.html", {
        "attendances": records,
        "present_count": present_count,
        "absent_count": absent_count,
        "classes": classes,
        "selected_date": selected_date,
        "selected_class": selected_class,
    })


# =====================================================
# 🤖 LIVE MULTI-CAMERA FACE ATTENDANCE
# =====================================================

def generate_frames(camera_id):

    #video_capture = cv2.VideoCapture(int(camera_id))

    #video_capture.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
    #video_capture.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)

    from collections import deque
    from datetime import date

    global LIVE_MESSAGES
    LIVE_MESSAGES = deque(maxlen=10)

    # 🔐 Unknown cooldown system (10 seconds)
    last_unknown_save_time = 0

    # Load known faces
    students = StudentFaceData.objects.all()

    known_encodings = []
    known_students = []

    for student_face in students:
        encoding = np.frombuffer(student_face.encoding, dtype=np.float64)
        known_encodings.append(encoding)
        known_students.append(student_face.student)

    while True:
        success, frame = video_capture.read()
        if not success:
            break

        #rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):

            if len(known_encodings) > 0:

                distances = face_recognition.face_distance(known_encodings, face_encoding)
                best_match_index = np.argmin(distances)

                if distances[best_match_index] < 0.5:

                    student = known_students[best_match_index]

                    Attendance.objects.get_or_create(
                        student=student,
                        date=date.today(),
                        defaults={"status": "Present"}
                    )

                    message = f"{student.user.username} Marked Present ✅"
                    LIVE_MESSAGES.appendleft(message)

                    label = student.user.username
                    color = (0, 255, 0)

                else:
                    # 🔴 UNKNOWN FACE DETECTED
                    current_time = time.time()

                    if current_time - last_unknown_save_time > 10:

                        filename = f"{uuid.uuid4()}.jpg"
                        folder_path = os.path.join(settings.MEDIA_ROOT, "unknown_faces")
                        os.makedirs(folder_path, exist_ok=True)

                        filepath = os.path.join(folder_path, filename)

                        #cv2.imwrite(filepath, frame)

                        UnknownFace.objects.create(
                            image=f"unknown_faces/{filename}"
                        )

                        last_unknown_save_time = current_time

                    message = "Unknown Face ❌"
                    LIVE_MESSAGES.appendleft(message)

                    label = "Unknown"
                    color = (0, 0, 255)

            else:
                label = "No Data"
                color = (0, 0, 255)

            #cv2.rectangle(frame, (left, top), (right, bottom), color, 2)
            #cv2.putText(frame, label, (left, top - 10),
                        #cv2.FONT_HERSHEY_SIMPLEX, 0.8, color, 2)

        #ret, buffer = cv2.imencode('.jpg', frame)
        frame = buffer.tobytes()

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame + b'\r\n')

@staff_member_required
def video_feed(request, camera_id):
    return StreamingHttpResponse(
        generate_frames(camera_id),
        content_type="multipart/x-mixed-replace; boundary=frame"
    )


@staff_member_required
def live_attendance_page(request):
    auto_mark_absent()   # 🔥 auto absent check
    return render(request, "attendance/live_attendance.html")

# =====================================================
# 📊 Attendance Analytics
# =====================================================

def attendance_analytics(request):

    students = Student.objects.all()
    analytics = []

    for student in students:
        total = Attendance.objects.filter(student=student).count()
        present = Attendance.objects.filter(student=student, status="Present").count()

        percentage = (present / total * 100) if total > 0 else 0

        analytics.append({
            "student": student,
            "percentage": round(percentage, 2)
        })

    analytics.sort(key=lambda x: x["percentage"])

    return render(request, "attendance/analytics.html", {
        "analytics": analytics
    })

# =====================================================
# 👤 Student Self Attendance
# =====================================================

@login_required
def student_attendance(request):
    student = Student.objects.filter(user=request.user).first()

    if not student:
        messages.error(request, "Student profile not found.")
        return redirect("login")

    records = Attendance.objects.filter(student=student)

    return render(request, "attendance/student_attendance.html", {
        "records": records
    })

# =====================================================
# 🤖 Face Attendance Page
# =====================================================

from django.contrib.auth.decorators import login_required

@login_required
def face_attendance(request):
    return render(request, "attendance/face_attendance.html")


# =====================================================
# 🤖 Mark Attendance By Face (Single Capture Mode)
# =====================================================

@login_required
def mark_attendance_by_face(request):

    from attendance.face_engine import recognize_face_from_camera

    student = recognize_face_from_camera()

    if student is None:
        messages.error(request, "No matching student found ❌")
        return redirect("admin_dashboard")

    today = date.today()

    already_marked = Attendance.objects.filter(
        student=student,
        date=today
    ).exists()

    if not already_marked:
        Attendance.objects.create(
            student=student,
            date=today,
            status="Present"
        )
        messages.success(request, f"{student.user.username} Attendance Marked ✅")
    else:
        messages.warning(request, "Attendance already marked today ⚠️")

    return redirect("admin_dashboard")


from django.utils.timezone import now
from datetime import time
from accounts.models import Student
from attendance.models import Attendance

def auto_mark_absent():

    current_time = now().time()

    # Only run after 10:00 AM
    if current_time < time(10, 1):
        return

    today = now().date()

    students = Student.objects.all()

    for student in students:

        already_marked = Attendance.objects.filter(
            student=student,
            date=today
        ).exists()

        if not already_marked:
            Attendance.objects.create(
                student=student,
                date=today,
                status="Absent"
            )

from .models import UnknownFace

def unknown_faces_list(request):
    faces = UnknownFace.objects.order_by("-captured_at")
    return render(request, "attendance/unknown_faces.html", {
        "faces": faces
    })


import face_recognition
import numpy as np
import pickle
from django.shortcuts import redirect
from .models import UnknownFace, StudentFaceData
from .forms import ConvertUnknownForm


def convert_unknown_to_student(request, face_id):

    face = UnknownFace.objects.get(id=face_id)

    if request.method == "POST":
        form = ConvertUnknownForm(request.POST)

        if form.is_valid():

            student = form.cleaned_data["student"]

            image_path = face.image.path
            image = face_recognition.load_image_file(image_path)

            encodings = face_recognition.face_encodings(image)

            if encodings:

                encoding = encodings[0]

                StudentFaceData.objects.update_or_create(
                    student=student,
                    defaults={
                        "encoding": pickle.dumps(encoding)
                    }
                )

                face.delete()

            return redirect("unknown_faces")

    else:
        form = ConvertUnknownForm()

    return render(request, "attendance/convert_unknown.html", {
        "form": form,
        "face": face
    })