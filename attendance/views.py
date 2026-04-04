"""
Attendance Views Module

This module handles all views related to attendance including:
- Face encoding upload
- Manual attendance marking
- Attendance reports
- Live face recognition camera streams
- Attendance analytics
- Unknown face management
"""

try:
    import cv2
except ModuleNotFoundError:
    cv2 = None

try:
    import numpy as np
except ModuleNotFoundError:
    np = None

try:
    import face_recognition
except ModuleNotFoundError:
    face_recognition = None

import pickle
import os
import threading
import textwrap
import uuid
import time
import logging
from urllib.parse import urlencode
from collections import deque
from datetime import date as dt_date

from django.conf import settings
from django.db import close_old_connections, transaction
from django.db.models import Q, Count, Prefetch
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.http import StreamingHttpResponse, JsonResponse, HttpResponse
from django.urls import reverse
from django.utils import timezone
from django.utils.timezone import localdate
from django.views.decorators.http import require_POST
from django.core.files.base import ContentFile

from .models import Attendance, StudentFaceData, ClassroomCamera, UnknownFace
from .forms import FaceUploadForm, ConvertUnknownForm
from .services import save_attendance_record
from .utils import send_attendance_email
from .auto_absent import mark_auto_absent
from accounts.models import Classroom, Student, CustomUser
from accounts.forms import DEFAULT_PASSWORD, build_student_username, split_full_name


# =====================================================
# STREAM CONFIGURATION
# =====================================================

LIVE_MESSAGES = deque(maxlen=10)
CAMERA_STREAMS = {}
CAMERA_STREAMS_LOCK = threading.Lock()

# Stream settings
STREAM_WIDTH = 640
STREAM_HEIGHT = 480
STREAM_FPS = 20
STREAM_JPEG_QUALITY = 72
STREAM_IDLE_TIMEOUT_SECONDS = 8
STREAM_FRAME_WAIT_SECONDS = 5
CAMERA_INITIALIZATION_WAIT_SECONDS = 2.2
CAMERA_WARMUP_READ_ATTEMPTS = 8
CAMERA_SCAN_FALLBACK_INDICES = (0, 1, 2, 3)
CAMERA_INDEX_CACHE_TTL_SECONDS = 300
KNOWN_FACE_REFRESH_SECONDS = 15
RECOGNITION_FRAME_INTERVAL = 2
RECOGNITION_SCALE = 0.5
MATCH_THRESHOLD = 0.62
MIN_FACE_BOX_SIZE = 36
UNKNOWN_FACE_SAVE_INTERVAL_SECONDS = 10
CAMERA_INDEX_CACHE = {}
CAMERA_INDEX_CACHE_LOCK = threading.Lock()

LOGGER = logging.getLogger(__name__)
CAMERA_STACK_AVAILABLE = cv2 is not None and face_recognition is not None and np is not None

if cv2 is not None:
    cv2.setUseOptimized(True)


# =====================================================
# ROLE CHECK HELPERS (shared with accounts)
# =====================================================

def is_admin_user(user):
    """Check if user is an authenticated admin."""
    return user.is_authenticated and getattr(user, "role", "") == "ADMIN"


def is_teacher_or_admin(user):
    """Check if user is either admin or teacher."""
    return user.is_authenticated and (
        getattr(user, "role", "") in {"ADMIN", "TEACHER"} or getattr(user, "is_superuser", False)
    )


# =====================================================
# UTILITY FUNCTIONS
# =====================================================

def parse_attendance_date(raw_value):
    """Parse attendance date from string or return today's date."""
    if not raw_value:
        return localdate()
    try:
        return dt_date.fromisoformat(raw_value)
    except ValueError:
        return localdate()


def normalize_class_label(value):
    """Normalize class label for comparison."""
    normalized = (value or "").strip().lower()
    normalized = normalized.replace(" ", "").replace("-", "").replace("_", "")
    if normalized.startswith("class"):
        normalized = normalized[5:]
    return normalized


def resolve_selected_class(raw_value, available_classes):
    """Resolve selected class from raw input against available classes."""
    candidate = (raw_value or "").strip()
    if not candidate:
        return None
    if candidate in available_classes:
        return candidate
    normalized_lookup = {
        normalize_class_label(name): name for name in available_classes
    }
    return normalized_lookup.get(normalize_class_label(candidate))


def filter_attendance_by_class(queryset, class_name):
    """Filter attendance queryset by class name."""
    return queryset.filter(
        Q(student_class=class_name) | Q(student_class="", student__class_name=class_name)
    )


def filter_attendance_by_classes(queryset, class_names):
    """Filter attendance queryset by multiple class names."""
    if not class_names:
        return queryset.none()
    return queryset.filter(
        Q(student_class__in=class_names) | Q(student_class="", student__class_name__in=class_names)
    )


def push_live_message(message):
    """Add a message to the live message queue."""
    if not LIVE_MESSAGES or LIVE_MESSAGES[0] != message:
        LIVE_MESSAGES.appendleft(message)


# =====================================================
# CAMERA STREAM UTILITIES
# =====================================================

def encode_stream_frame(frame):
    """Encode a frame to JPEG bytes for streaming."""
    if cv2 is None or frame is None:
        return None
    success, buffer = cv2.imencode(
        ".jpg", frame, [int(cv2.IMWRITE_JPEG_QUALITY), STREAM_JPEG_QUALITY]
    )
    if not success:
        return None
    return b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + buffer.tobytes() + b"\r\n"


def get_capture_backends():
    """Get available camera capture backends for the platform."""
    if cv2 is None:
        return [("Unavailable", None)]
    backends = []
    if os.name == "nt":
        if hasattr(cv2, "CAP_DSHOW"):
            backends.append(("DirectShow", cv2.CAP_DSHOW))
        if hasattr(cv2, "CAP_MSMF"):
            backends.append(("Media Foundation", cv2.CAP_MSMF))
    elif hasattr(cv2, "CAP_V4L2"):
        backends.append(("V4L2", cv2.CAP_V4L2))
    backends.append(("Auto", None))
    return backends


CAPTURE_BACKENDS = get_capture_backends()


def configure_capture(capture):
    """Configure camera capture settings for optimal performance."""
    if cv2 is None:
        return
    if hasattr(cv2, "CAP_PROP_OPEN_TIMEOUT_MSEC"):
        capture.set(cv2.CAP_PROP_OPEN_TIMEOUT_MSEC, 1200)
    if hasattr(cv2, "CAP_PROP_READ_TIMEOUT_MSEC"):
        capture.set(cv2.CAP_PROP_READ_TIMEOUT_MSEC, 1200)
    if hasattr(cv2, "CAP_PROP_FOURCC"):
        capture.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))
    if hasattr(cv2, "CAP_PROP_BUFFERSIZE"):
        capture.set(cv2.CAP_PROP_BUFFERSIZE, 1)
    capture.set(cv2.CAP_PROP_FRAME_WIDTH, STREAM_WIDTH)
    capture.set(cv2.CAP_PROP_FRAME_HEIGHT, STREAM_HEIGHT)
    capture.set(cv2.CAP_PROP_FPS, STREAM_FPS)


def get_cached_camera_index(requested_index):
    """Get cached camera index if not expired."""
    with CAMERA_INDEX_CACHE_LOCK:
        entry = CAMERA_INDEX_CACHE.get(requested_index)
        if not entry:
            return None
        if entry["expires_at"] <= time.time():
            CAMERA_INDEX_CACHE.pop(requested_index, None)
            return None
        return entry["resolved_index"]


def cache_camera_index(requested_index, resolved_index):
    """Cache resolved camera index with TTL."""
    with CAMERA_INDEX_CACHE_LOCK:
        CAMERA_INDEX_CACHE[requested_index] = {
            "resolved_index": resolved_index,
            "expires_at": time.time() + CAMERA_INDEX_CACHE_TTL_SECONDS,
        }


def get_reserved_capture_indices(exclude_camera_id=None):
    """Get set of reserved camera indices from active streams."""
    reserved = set()
    with CAMERA_STREAMS_LOCK:
        for stream_id, stream in CAMERA_STREAMS.items():
            if stream_id == exclude_camera_id or not stream or stream.stop_event.is_set():
                continue
            if stream.resolved_capture_index and stream.thread and stream.thread.is_alive():
                reserved.add(stream.resolved_capture_index)
    return reserved


def build_candidate_indices(requested_index, exclude_camera_id=None):
    """Build ordered list of camera indices to try."""
    reserved_indices = get_reserved_capture_indices(exclude_camera_id=exclude_camera_id)
    cached_index = get_cached_camera_index(requested_index)
    candidates = [requested_index]
    if cached_index is not None:
        candidates.append(cached_index)
    if requested_index != 0:
        candidates.append(0)
    candidates.extend(CAMERA_SCAN_FALLBACK_INDICES)

    ordered = []
    for candidate in candidates:
        if candidate is None or candidate < 0 or candidate in ordered:
            continue
        if candidate in reserved_indices and candidate != requested_index:
            continue
        ordered.append(candidate)

    return ordered if ordered else [max(0, requested_index)]


def build_status_frame(message, detail=None, hint=None):
    """Build a status display frame when camera is unavailable."""
    if np is None:
        return None
    frame = np.zeros((STREAM_HEIGHT, STREAM_WIDTH, 3), dtype=np.uint8)
    frame[:] = (14, 22, 37)
    if cv2 is None:
        return frame

    cv2.putText(frame, "Live Attendance Feed", (32, 88), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (197, 228, 255), 2)
    cv2.putText(frame, message, (32, 160), cv2.FONT_HERSHEY_SIMPLEX, 0.8, (120, 220, 255), 2)

    detail_lines = textwrap.wrap(detail or "", width=46)[:2]
    hint_text = hint or "Close Camera or Zoom and check Windows camera permissions."
    y_position = 220

    for line in detail_lines:
        cv2.putText(frame, line, (32, y_position), cv2.FONT_HERSHEY_SIMPLEX, 0.58, (182, 206, 234), 1)
        y_position += 28

    cv2.putText(
        frame, hint_text, (32, min(y_position + 12, STREAM_HEIGHT - 24)),
        cv2.FONT_HERSHEY_SIMPLEX, 0.52, (170, 190, 215), 1
    )
    return frame


# =====================================================
# CAMERA STREAM WORKER
# =====================================================

class CameraStreamWorker:
    """Worker class managing a single camera stream for face recognition."""

    def __init__(self, camera_id, capture_index):
        self.camera_id = camera_id
        self.requested_capture_index = capture_index
        self.capture_index = capture_index
        self.thread = None
        self.thread_lock = threading.Lock()
        self.stop_event = threading.Event()
        self.initialized_event = threading.Event()
        self.frame_condition = threading.Condition()
        self.latest_frame = encode_stream_frame(build_status_frame("Starting camera..."))
        self.frame_version = 0
        self.active_clients = 0
        self.last_accessed_at = time.time()
        self.last_unknown_save_time = 0
        self.known_encodings = []
        self.known_encodings_matrix = np.empty((0, 128), dtype=np.float64)
        self.known_students = []
        self.known_faces_loaded_at = 0
        self.attendance_state_cache = {}
        self.cached_detections = []
        self.capture = None
        self.available = None
        self.status_message = "Starting camera..."
        self.status_detail = f"Trying configured camera index {capture_index}."
        self.capture_backend_name = None
        self.resolved_capture_index = None
        self.attempted_sources = []

    def _normalize_encoding_vector(self, encoding):
        """Normalize face encoding vector to standard format."""
        if encoding is None:
            return None
        try:
            vector = np.asarray(encoding, dtype=np.float64).reshape(-1)
        except Exception:
            return None
        if vector.shape[0] != 128 or not np.isfinite(vector).all():
            return None
        return np.ascontiguousarray(vector, dtype=np.float64)

    def _encoding_from_image_path(self, image_path):
        """Extract face encoding from image file."""
        if not image_path or not os.path.exists(image_path):
            return None
        try:
            image = face_recognition.load_image_file(image_path)
            face_locations = face_recognition.face_locations(
                image, number_of_times_to_upsample=1, model="hog"
            )
            if not face_locations:
                return None
            largest_face = max(
                face_locations,
                key=lambda box: max(1, (box[2] - box[0]) * (box[1] - box[3])),
            )
            encodings = face_recognition.face_encodings(
                image, known_face_locations=[largest_face], num_jitters=1
            )
            if not encodings:
                return None
            return self._normalize_encoding_vector(encodings[0])
        except Exception:
            LOGGER.exception("Failed to build encoding from image path: %s", image_path)
            return None

    def start(self):
        """Start the camera stream thread."""
        with self.thread_lock:
            if self.thread and self.thread.is_alive():
                return
            self.thread = threading.Thread(
                target=self._run, daemon=True, name=f"camera-stream-{self.camera_id}"
            )
            self.thread.start()

    def wait_until_initialized(self, timeout=CAMERA_INITIALIZATION_WAIT_SECONDS):
        """Wait for camera initialization to complete."""
        return self.initialized_event.wait(timeout=timeout)

    def get_status_payload(self):
        """Get current camera status for JSON response."""
        attempted_indices = []
        for index, _ in self.attempted_sources:
            if index not in attempted_indices:
                attempted_indices.append(index)
        return {
            "available": self.available,
            "status": self.status_message,
            "detail": self.status_detail,
            "requested_index": self.requested_capture_index,
            "active_index": self.resolved_capture_index,
            "backend": self.capture_backend_name,
            "attempted_indices": attempted_indices,
        }

    def _update_status(self, message, detail=None, available=None):
        """Update camera status message."""
        with self.frame_condition:
            self.status_message = message
            self.status_detail = detail or ""
            if available is not None:
                self.available = available

    def touch(self):
        """Update last accessed timestamp."""
        with self.frame_condition:
            self.last_accessed_at = time.time()

    def add_client(self):
        """Register a new client viewer."""
        with self.frame_condition:
            self.active_clients += 1
            self.last_accessed_at = time.time()

    def remove_client(self):
        """Unregister a client viewer."""
        with self.frame_condition:
            self.active_clients = max(0, self.active_clients - 1)
            self.last_accessed_at = time.time()
            self.frame_condition.notify_all()

    def request_shutdown(self, immediate=False):
        """Request camera stream shutdown."""
        with self.frame_condition:
            self.stop_event.set()
            if immediate:
                self.active_clients = 0
                self.last_accessed_at = 0
            self.frame_condition.notify_all()
        self.initialized_event.set()

        if immediate and self.capture is not None:
            try:
                self.capture.release()
            except Exception:
                pass
        if immediate and self.thread and self.thread.is_alive():
            self.thread.join(timeout=1.5)

    def wait_for_frame(self, last_version, timeout=STREAM_FRAME_WAIT_SECONDS):
        """Wait for new frame with timeout."""
        with self.frame_condition:
            self.last_accessed_at = time.time()
            deadline = time.time() + timeout
            while True:
                if self.latest_frame is not None and self.frame_version != last_version:
                    return self.latest_frame, self.frame_version
                if self.stop_event.is_set():
                    return None, last_version
                remaining = deadline - time.time()
                if remaining <= 0:
                    break
                self.frame_condition.wait(timeout=remaining)
            return (None, last_version) if self.stop_event.is_set() else (self.latest_frame, self.frame_version)

    def _set_latest_frame(self, frame):
        """Set the latest processed frame."""
        payload = encode_stream_frame(frame)
        if payload is None:
            return
        with self.frame_condition:
            self.latest_frame = payload
            self.frame_version += 1
            self.last_accessed_at = time.time()
            self.frame_condition.notify_all()

    def _should_shutdown(self):
        """Check if stream should shutdown due to inactivity."""
        with self.frame_condition:
            return self.active_clients == 0 and (time.time() - self.last_accessed_at) > STREAM_IDLE_TIMEOUT_SECONDS

    def _probe_capture(self, candidate_index, backend_name, backend_flag):
        """Probe a single camera source for availability."""
        try:
            capture = cv2.VideoCapture(candidate_index, backend_flag) if backend_flag else cv2.VideoCapture(candidate_index)
        except Exception:
            return None, None
        if capture is None or not capture.isOpened():
            try:
                capture.release()
            except Exception:
                pass
            return None, None

        configure_capture(capture)
        for _ in range(CAMERA_WARMUP_READ_ATTEMPTS):
            if self.stop_event.is_set():
                capture.release()
                return None, None
            success, frame = capture.read()
            if success and frame is not None and getattr(frame, "size", 0):
                self.capture_backend_name = backend_name
                self.resolved_capture_index = candidate_index
                self.capture_index = candidate_index
                return capture, frame
            time.sleep(0.05)

        capture.release()
        return None, None

    def _build_capture(self):
        """Build camera capture by trying multiple indices and backends."""
        self.attempted_sources = []
        candidate_indices = build_candidate_indices(self.requested_capture_index, exclude_camera_id=self.camera_id)
        probe_detail = "Trying camera indices {}.".format(", ".join(str(i) for i in candidate_indices))
        self._update_status("Starting camera...", detail=probe_detail)

        for candidate_index in candidate_indices:
            for backend_name, backend_flag in CAPTURE_BACKENDS:
                self.attempted_sources.append((candidate_index, backend_name))
                capture, first_frame = self._probe_capture(candidate_index, backend_name, backend_flag)
                if capture is None:
                    continue

                cache_camera_index(self.requested_capture_index, candidate_index)
                success_detail = f"Using camera {candidate_index} via {backend_name}."
                if candidate_index != self.requested_capture_index:
                    success_detail += f" Configured index {self.requested_capture_index} was unavailable."
                self._update_status("Camera ready.", detail=success_detail, available=True)
                self.initialized_event.set()
                return capture, first_frame

        unavailable_detail = "Tried camera indices {}.".format(", ".join(str(i) for i in candidate_indices))
        unavailable_detail += " Close other camera apps and verify camera access."
        self._update_status("Camera unavailable.", detail=unavailable_detail, available=False)
        self.initialized_event.set()
        return None, None

    def _refresh_known_faces(self, force=False):
        """Load and cache face encodings for all students."""
        current_time = time.time()
        if not force and (current_time - self.known_faces_loaded_at) < KNOWN_FACE_REFRESH_SECONDS:
            return

        close_old_connections()
        known_encodings = []
        known_students = []

        face_rows = StudentFaceData.objects.select_related("student__user").all()
        face_by_student_id = {row.student_id: row for row in face_rows}
        students = Student.objects.select_related("user").all()

        for student in students:
            student_face = face_by_student_id.get(student.id)
            vector = None

            if student_face and student_face.encoding:
                try:
                    vector = self._normalize_encoding_vector(student_face.get_encoding())
                except Exception:
                    vector = None

            if vector is None:
                candidate_paths = [
                    getattr(student_face.image, "path", None) if student_face and student_face.image else None,
                    getattr(student.image, "path", None) if student.image else None,
                ]
                for image_path in candidate_paths:
                    if image_path:
                        vector = self._encoding_from_image_path(image_path)
                        if vector is not None:
                            break

                if vector is not None:
                    try:
                        if student_face is None:
                            student_face = StudentFaceData(student=student)
                            face_by_student_id[student.id] = student_face
                        student_face.set_encoding(vector)
                        student_face.save()
                    except Exception:
                        LOGGER.exception("Failed to persist encoding for student_id=%s", student.id)

            if vector is None:
                continue

            known_encodings.append(vector)
            known_students.append(student)

        self.known_encodings = known_encodings
        self.known_encodings_matrix = (
            np.ascontiguousarray(np.vstack(known_encodings), dtype=np.float64)
            if known_encodings else np.empty((0, 128), dtype=np.float64)
        )
        self.known_students = known_students
        self.known_faces_loaded_at = current_time
        push_live_message(f"Loaded {len(self.known_students)} registered face profiles")

    def _mark_student_present(self, student):
        """Mark a student as present and cache the result."""
        close_old_connections()
        attendance_date = localdate()
        student_id = getattr(student, "id", None)
        if not student_id:
            return "not_registered"

        cache_entry = self.attendance_state_cache.get(student_id)
        if cache_entry and cache_entry["date"] == attendance_date:
            return cache_entry.get("state", "already_marked")

        try:
            attendance, created, updated = save_attendance_record(
                student=student, status="Present", marked_by="FACE",
                attendance_date=attendance_date, marked_at=timezone.now(), overwrite_existing=True,
            )
        except Exception:
            LOGGER.exception("Failed to save attendance for student_id=%s", student_id)
            self.attendance_state_cache[student_id] = {"date": attendance_date, "state": "not_registered"}
            push_live_message(f"Student profile missing for id {student_id}")
            return "not_registered"

        state_changed = created or updated
        state = "already_marked" if not state_changed else "marked"
        self.attendance_state_cache[student_id] = {"date": attendance_date, "state": state}

        if state_changed:
            push_live_message(f"{student.user.get_full_name() or student.user.username} marked present")
        return state

    def _save_unknown_face(self, frame, top, right, bottom, left):
        """Save detected unknown face to database."""
        current_time = time.time()
        if current_time - self.last_unknown_save_time <= UNKNOWN_FACE_SAVE_INTERVAL_SECONDS:
            return

        top, right, bottom, left = max(top, 0), min(right, frame.shape[1]), min(bottom, frame.shape[0]), max(left, 0)
        face_crop = frame[top:bottom, left:right]
        if face_crop.size == 0:
            return

        folder = os.path.join(settings.MEDIA_ROOT, "unknown_faces")
        os.makedirs(folder, exist_ok=True)
        filepath = os.path.join(folder, f"{uuid.uuid4()}.jpg")
        cv2.imwrite(filepath, face_crop)

        close_old_connections()
        UnknownFace.objects.create(image=f"unknown_faces/{os.path.basename(filepath)}")
        self.last_unknown_save_time = current_time
        push_live_message("Unknown face detected")

    def _detect_faces(self, frame):
        """Detect and match faces using preloaded encodings."""
        reduced_frame = cv2.resize(frame, (0, 0), fx=RECOGNITION_SCALE, fy=RECOGNITION_SCALE)
        rgb_frame = np.ascontiguousarray(cv2.cvtColor(reduced_frame, cv2.COLOR_BGR2RGB))

        face_locations = face_recognition.face_locations(rgb_frame, number_of_times_to_upsample=0, model="hog")
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations, num_jitters=1)

        detections = []
        inverse_scale = 1.0 / RECOGNITION_SCALE

        for (top, right, bottom, left), face_encoding in zip(face_locations, face_encodings):
            scaled_top, scaled_right = int(top * inverse_scale), int(right * inverse_scale)
            scaled_bottom, scaled_left = int(bottom * inverse_scale), int(left * inverse_scale)

            if (scaled_bottom - scaled_top) < MIN_FACE_BOX_SIZE or (scaled_right - scaled_left) < MIN_FACE_BOX_SIZE:
                continue

            label, color = "Unknown", (0, 0, 255)

            if self.known_encodings_matrix.size:
                distances = face_recognition.face_distance(self.known_encodings_matrix, face_encoding)
                best_match_index = int(np.argmin(distances))
                best_distance = float(distances[best_match_index])
                matches = face_recognition.compare_faces(self.known_encodings_matrix, face_encoding, tolerance=MATCH_THRESHOLD)

                if matches[best_match_index] and best_distance <= MATCH_THRESHOLD:
                    student = self.known_students[best_match_index]
                    student_name = student.user.get_full_name() or student.user.username
                    attendance_state = self._mark_student_present(student)

                    if attendance_state == "marked":
                        label, color = f"{student_name} - Attendance Marked", (0, 255, 0)
                    elif attendance_state == "already_marked":
                        label, color = f"{student_name} - Already Marked", (0, 215, 255)
                else:
                    self._save_unknown_face(frame, scaled_top, scaled_right, scaled_bottom, scaled_left)
            else:
                self._save_unknown_face(frame, scaled_top, scaled_right, scaled_bottom, scaled_left)

            detections.append({
                "top": scaled_top, "right": scaled_right, "bottom": scaled_bottom, "left": scaled_left,
                "label": label, "color": color,
            })

        return detections

    def _draw_detections(self, frame):
        """Draw detection boxes and labels on frame."""
        rendered_frame = frame.copy()
        for detection in self.cached_detections:
            cv2.rectangle(rendered_frame, (detection["left"], detection["top"]),
                          (detection["right"], detection["bottom"]), detection["color"], 2)
            cv2.putText(rendered_frame, detection["label"],
                        (detection["left"], max(24, detection["top"] - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.75, detection["color"], 2)
        return rendered_frame

    def _run(self):
        """Main camera stream processing loop."""
        close_old_connections()
        if not CAMERA_STACK_AVAILABLE:
            self._set_latest_frame(build_status_frame("Camera dependencies unavailable", detail="Install opencv-python and face_recognition."))
            self.initialized_event.set()
            while not self.stop_event.is_set() and not self._should_shutdown():
                time.sleep(0.3)
            self._cleanup()
            return

        self._refresh_known_faces(force=True)
        capture, initial_frame = self._build_capture()
        self.capture = capture

        if capture is None:
            while not self.stop_event.is_set() and not self._should_shutdown():
                self._set_latest_frame(build_status_frame(self.status_message, detail=self.status_detail))
                time.sleep(0.5)
            self.capture = None
            self._cleanup()
            return

        self.initialized_event.set()

        if initial_frame is not None:
            if initial_frame.shape[1] != STREAM_WIDTH or initial_frame.shape[0] != STREAM_HEIGHT:
                initial_frame = cv2.resize(initial_frame, (STREAM_WIDTH, STREAM_HEIGHT))
            self._set_latest_frame(initial_frame)
        else:
            for _ in range(4):
                success, frame = capture.read()
                if success:
                    self._set_latest_frame(cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT)))
                    break
                time.sleep(0.05)

        frame_counter = 0
        try:
            while not self.stop_event.is_set():
                if self._should_shutdown():
                    break

                success, frame = capture.read()
                if not success:
                    self._set_latest_frame(build_status_frame("No frame received from camera."))
                    time.sleep(0.2)
                    continue

                if frame.shape[1] != STREAM_WIDTH or frame.shape[0] != STREAM_HEIGHT:
                    frame = cv2.resize(frame, (STREAM_WIDTH, STREAM_HEIGHT))

                frame_counter += 1
                if not self.cached_detections or frame_counter % RECOGNITION_FRAME_INTERVAL == 0:
                    self.cached_detections = self._detect_faces(frame)

                self._set_latest_frame(self._draw_detections(frame))
        finally:
            self.capture = None
            capture.release()
            close_old_connections()
            self._cleanup()

    def _cleanup(self):
        """Clean up stream from global registry."""
        with CAMERA_STREAMS_LOCK:
            if CAMERA_STREAMS.get(self.camera_id) is self:
                CAMERA_STREAMS.pop(self.camera_id, None)


# =====================================================
# CAMERA STREAM MANAGEMENT
# =====================================================

def get_or_create_camera_stream(camera_id):
    """Get or create a camera stream worker for the given camera ID."""
    camera_config = ClassroomCamera.objects.filter(id=camera_id).first()
    capture_index = camera_config.camera_index if camera_config else int(camera_id)

    while True:
        stale_stream = None
        created_stream = None

        with CAMERA_STREAMS_LOCK:
            stream = CAMERA_STREAMS.get(camera_id)
            if stream and stream.thread and stream.thread.is_alive() and not stream.stop_event.is_set():
                stream.touch()
                return stream
            stale_stream = stream if stream else None
            created_stream = CameraStreamWorker(camera_id=camera_id, capture_index=capture_index)
            CAMERA_STREAMS[camera_id] = created_stream

        if stale_stream:
            stale_stream.request_shutdown(immediate=True)
            continue

        created_stream.start()
        return created_stream


def stop_camera_stream(camera_id, immediate=True):
    """Stop a camera stream and clean up resources."""
    with CAMERA_STREAMS_LOCK:
        stream = CAMERA_STREAMS.get(camera_id)
    if stream is None:
        return False

    stream.request_shutdown(immediate=immediate)
    with CAMERA_STREAMS_LOCK:
        current_stream = CAMERA_STREAMS.get(camera_id)
        if current_stream is stream and not (stream.thread and stream.thread.is_alive()):
            CAMERA_STREAMS.pop(camera_id, None)
    return True


def generate_frames(camera_id):
    """Generator yielding camera frame bytes for streaming response."""
    if not CAMERA_STACK_AVAILABLE:
        return

    stream = get_or_create_camera_stream(camera_id)
    stream.add_client()
    frame_version = -1

    try:
        while True:
            payload, next_version = stream.wait_for_frame(frame_version, timeout=0.8)
            if payload is None and stream.stop_event.is_set():
                break
            if payload and next_version != frame_version:
                frame_version = next_version
                yield payload
            else:
                time.sleep(0.01)
    finally:
        stream.remove_client()


# =====================================================
# LIVE ATTENDANCE FEED
# =====================================================

@login_required
@user_passes_test(is_admin_user)
def live_messages(request):
    """Return current live messages for the dashboard."""
    return JsonResponse({"messages": list(LIVE_MESSAGES)})


# =====================================================
# FACE ENCODING UPLOAD
# =====================================================

@login_required
@user_passes_test(is_admin_user)
def upload_face(request, student_id):
    """Upload and encode face for a student."""
    student = get_object_or_404(Student, id=student_id)

    if face_recognition is None:
        messages.error(request, "face_recognition dependency is missing. Install it to upload and encode faces.")
        return redirect("admin_dashboard")

    if request.method == "POST":
        form = FaceUploadForm(request.POST, request.FILES)
        if form.is_valid():
            image_file = form.cleaned_data["image"]
            image = face_recognition.load_image_file(image_file)
            encodings = face_recognition.face_encodings(image)

            if encodings:
                face_data, _ = StudentFaceData.objects.get_or_create(student=student)
                face_data.encoding = pickle.dumps(encodings[0])
                face_data.save()
                messages.success(request, "Face uploaded successfully")
                return redirect("admin_dashboard")
            form.add_error(None, "No face detected!")
    else:
        form = FaceUploadForm()

    return render(request, "attendance/upload_faces.html", {"form": form, "student": student})


# =====================================================
# MANUAL ATTENDANCE
# =====================================================

@login_required
@user_passes_test(is_teacher_or_admin)
def mark_attendance(request):
    """Mark manual attendance for students."""
    selected_class_raw = request.GET.get("class") or request.POST.get("class")
    selected_date_raw = request.GET.get("date") or request.POST.get("date")
    selected_date = parse_attendance_date(selected_date_raw)

    # Determine available classes based on user role
    if hasattr(request.user, "teacher"):
        teacher = request.user.teacher
        class_names = list(teacher.classes.values_list("name", flat=True))
        if not class_names:
            messages.error(request, "Your classes are not assigned. Please contact admin.")
            return redirect("teacher_dashboard")

        selected_class_input = (selected_class_raw or "").strip()
        selected_class = resolve_selected_class(selected_class_raw, class_names)
        has_invalid_teacher_class = bool(selected_class_input and not selected_class)
        allowed_students = Student.objects.filter(class_name__in=class_names).select_related("user")
        students = allowed_students.filter(class_name=selected_class) if selected_class else Student.objects.none()

        if request.method == "GET" and has_invalid_teacher_class:
            messages.error(request, f"You are not assigned to class '{selected_class_input}'. Select one of your assigned classes.")
    else:
        classes = list(Student.objects.values_list("class_name", flat=True).distinct())
        selected_class = resolve_selected_class(selected_class_raw, classes)
        has_invalid_teacher_class = False
        allowed_students = Student.objects.all().select_related("user")
        students = allowed_students.filter(class_name=selected_class) if selected_class else allowed_students

    # Store classes in a consistent variable
    available_classes = class_names if hasattr(request.user, "teacher") else classes

    if request.method == "POST":
        return _handle_attendance_submission(request, selected_class, selected_class_raw, selected_date, allowed_students, has_invalid_teacher_class)

    return render(request, "attendance/mark_attendance.html", {
        "students": students, "classes": available_classes,
        "selected_class": selected_class, "selected_date": selected_date.isoformat(),
    })


def _handle_attendance_submission(request, selected_class, selected_class_raw, selected_date, allowed_students, has_invalid_teacher_class):
    """Process attendance form submission."""
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest" or "application/json" in request.headers.get("Accept", "")

    if has_invalid_teacher_class:
        error_payload = {
            "success": False, "message": f"You are not assigned to class '{(selected_class_raw or '').strip()}'.",
            "created": 0, "updated": 0, "date": selected_date.isoformat(), "class": (selected_class_raw or "").strip(),
        }
        return JsonResponse(error_payload) if is_ajax else (messages.error(request, error_payload["message"]) or redirect("mark_attendance"))

    valid_statuses = {choice[0] for choice in Attendance.STATUS}
    posted_ids = set()
    for raw_id in request.POST.getlist("student_ids"):
        try:
            posted_ids.add(int(raw_id))
        except (TypeError, ValueError):
            continue

    for field_name, status_value in request.POST.items():
        if status_value not in valid_statuses:
            continue
        if field_name.startswith("attendance_"):
            raw_id = field_name[len("attendance_"):]
        elif field_name.startswith("status_"):
            raw_id = field_name[len("status_"):]
        else:
            continue
        try:
            posted_ids.add(int(raw_id))
        except (TypeError, ValueError):
            continue

    target_students = allowed_students
    if selected_class:
        target_students = target_students.filter(class_name=selected_class)
    if posted_ids:
        target_students = target_students.filter(id__in=posted_ids)
    else:
        target_students = target_students.none()

    submitted_count = created_count = updated_count = 0
    for student in target_students:
        status = request.POST.get(f"attendance_{student.id}") or request.POST.get(f"status_{student.id}")
        if status not in valid_statuses:
            continue
        submitted_count += 1
        _, created, updated = save_attendance_record(
            student=student, status=status, marked_by="MANUAL",
            attendance_date=selected_date, marked_at=timezone.now(), overwrite_existing=True,
        )
        if created:
            created_count += 1
        elif updated:
            updated_count += 1

    LOGGER.info(
        "Manual attendance: user_id=%s role=%s class=%s date=%s submitted=%s created=%s updated=%s",
        request.user.id, getattr(request.user, "role", ""), selected_class or "", selected_date,
        submitted_count, created_count, updated_count,
    )

    if submitted_count == 0:
        error_payload = {"success": False, "message": "No attendance status was selected.",
                        "created": 0, "updated": 0, "date": selected_date.isoformat(), "class": selected_class or ""}
        if is_ajax:
            return JsonResponse(error_payload)
        messages.error(request, "Please select attendance status for at least one student.")
        params = {"date": selected_date.isoformat()}
        if selected_class:
            params["class"] = selected_class
        return redirect(f"{reverse('mark_attendance')}?{urlencode(params)}")

    response_payload = {"success": True, "created": created_count, "updated": updated_count,
                        "date": selected_date.isoformat(), "class": selected_class or ""}
    if is_ajax:
        return JsonResponse(response_payload)

    messages.success(request, f"Attendance saved. Created: {created_count}, Updated: {updated_count}.")
    params = {"date": selected_date.isoformat()}
    if selected_class:
        params["class"] = selected_class
    return redirect(f"{reverse('attendance_report')}?{urlencode(params)}")


# =====================================================
# ATTENDANCE REPORT
# =====================================================

@login_required
@user_passes_test(is_teacher_or_admin)
def attendance_report(request):
    """Display attendance report for a date and class."""
    selected_date_raw = request.GET.get("date")
    selected_class = request.GET.get("class")
    selected_date = parse_attendance_date(selected_date_raw)

    if hasattr(request.user, "teacher"):
        teacher = request.user.teacher
        class_names = list(teacher.classes.values_list("name", flat=True))
        classes = class_names
        students_scope = Student.objects.filter(class_name__in=class_names)
        if selected_class and selected_class not in class_names:
            selected_class = None
    else:
        classes = list(Student.objects.values_list("class_name", flat=True).distinct())
        students_scope = Student.objects.all()

    if selected_class:
        students_scope = students_scope.filter(class_name=selected_class)

    total_students_count = students_scope.count()
    records = Attendance.objects.select_related("student__user").filter(date=selected_date)

    if selected_class:
        records = filter_attendance_by_class(records, selected_class)
    elif hasattr(request.user, "teacher"):
        records = filter_attendance_by_classes(records, class_names)

    records = records.order_by("student_class", "student__roll_number", "student__user__username")

    marked_count = records.values("student_id").distinct().count()
    present_count = records.filter(status="Present").values("student_id").distinct().count()
    absent_count = records.filter(status="Absent").values("student_id").distinct().count()

    LOGGER.info(
        "Attendance report: user_id=%s role=%s date=%s class=%s total=%s marked=%s present=%s absent=%s",
        request.user.id, getattr(request.user, "role", ""), selected_date, selected_class or "ALL",
        total_students_count, marked_count, present_count, absent_count,
    )

    return render(request, "attendance/attendance_report.html", {
        "attendances": records, "present_count": present_count, "absent_count": absent_count,
        "not_marked_count": max(total_students_count - marked_count, 0),
        "total_students_count": total_students_count, "marked_count": marked_count,
        "has_searched": True, "has_records": records.exists(),
        "classes": classes, "selected_date": selected_date.isoformat(), "selected_class": selected_class,
    })


# =====================================================
# LIVE FACE RECOGNITION
# =====================================================

@login_required
@user_passes_test(is_admin_user)
def video_feed(request, camera_id):
    """Stream video frames for a camera."""
    return StreamingHttpResponse(generate_frames(camera_id), content_type="multipart/x-mixed-replace; boundary=frame")


@login_required
@user_passes_test(is_admin_user)
def start_camera_feed(request, camera_id):
    """Start camera stream and return status."""
    if not CAMERA_STACK_AVAILABLE:
        return JsonResponse({
            "started": False, "initialized": False, "camera_id": camera_id,
            "resolution": f"{STREAM_WIDTH}x{STREAM_HEIGHT}", "status": "error",
            "message": "Install opencv-python and face_recognition to use live camera feed.",
        }, status=503)

    stream = get_or_create_camera_stream(camera_id)
    stream.touch()
    initialized = stream.wait_until_initialized()
    return JsonResponse({"started": True, "initialized": initialized, "camera_id": camera_id,
                         "resolution": f"{STREAM_WIDTH}x{STREAM_HEIGHT}", **stream.get_status_payload()})


@login_required
@user_passes_test(is_admin_user)
@require_POST
def stop_camera_feeds(request):
    """Stop multiple camera streams."""
    stopped_ids = []
    for value in request.POST.getlist("camera_ids"):
        try:
            camera_id = int(value)
            if stop_camera_stream(camera_id, immediate=True):
                stopped_ids.append(camera_id)
        except (TypeError, ValueError):
            continue
    return JsonResponse({"stopped": stopped_ids, "requested": len(request.POST.getlist("camera_ids"))})


# =====================================================
# ATTENDANCE ANALYTICS (Optimized with aggregation)
# =====================================================

@login_required
@user_passes_test(is_teacher_or_admin)
def attendance_analytics(request):
    """Display attendance analytics with optimized aggregation queries."""
    students = Student.objects.select_related("user").all()

    # Use aggregation to get counts per student in one query
    attendance_counts = Attendance.objects.values("student_id").annotate(
        total=Count("id"),
        present=Count("id", filter=Q(status="Present"))
    )

    # Build lookup dictionary for O(1) access
    counts_by_student = {item["student_id"]: item for item in attendance_counts}

    analytics = []
    for student in students:
        counts = counts_by_student.get(student.id, {"total": 0, "present": 0})
        total = counts["total"]
        present = counts["present"]
        percentage = (present / total * 100) if total > 0 else 0
        analytics.append({"student": student, "percentage": round(percentage, 2)})

    analytics.sort(key=lambda x: x["percentage"])
    return render(request, "attendance/analytics.html", {"analytics": analytics})


# =====================================================
# STUDENT SELF ATTENDANCE
# =====================================================

@login_required
def student_attendance(request):
    """Display student's own attendance records."""
    student = Student.objects.filter(user=request.user).first()
    if not student:
        messages.error(request, "Student profile not found")
        return redirect("login")
    return render(request, "attendance/student_attendance.html", {
        "records": Attendance.objects.filter(student=student)
    })


# =====================================================
# FACE ATTENDANCE
# =====================================================

@login_required
@user_passes_test(is_admin_user)
def face_attendance(request):
    """Render face attendance page."""
    return render(request, "attendance/face_attendance.html")


@login_required
@user_passes_test(is_admin_user)
def mark_attendance_by_face(request):
    """Mark attendance using face recognition."""
    try:
        from attendance.face_engine import recognize_face_from_camera
    except Exception:
        LOGGER.exception("Face engine import failed.")
        messages.error(request, "Face recognition dependencies are missing.")
        return redirect("admin_dashboard")

    try:
        student = recognize_face_from_camera()
    except Exception:
        LOGGER.exception("Face attendance capture failed.")
        messages.error(request, "Unable to access camera feed right now.")
        return redirect("admin_dashboard")

    if student is None:
        messages.error(request, "No matching student found")
        return redirect("admin_dashboard")

    today = localdate()
    attendance, created, updated = save_attendance_record(
        student=student, status="Present", marked_by="FACE",
        attendance_date=today, marked_at=timezone.now(), overwrite_existing=True,
    )

    LOGGER.info(
        "Face attendance: student_id=%s class=%s date=%s created=%s updated=%s status=%s",
        student.id, student.class_name, today, created, updated, attendance.status,
    )

    if created or updated:
        messages.success(request, f"{student.user.username} attendance marked Present.")
    else:
        messages.warning(request, "Attendance already marked as Present.")
    return redirect("admin_dashboard")


# =====================================================
# AUTO ABSENT SYSTEM
# =====================================================

def auto_mark_absent():
    """Trigger automatic absent marking for unmarked students."""
    return mark_auto_absent()


# =====================================================
# UNKNOWN FACES MANAGEMENT
# =====================================================

@login_required
@user_passes_test(is_admin_user)
def unknown_faces_list(request):
    """List unknown faces captured by the system."""
    faces = UnknownFace.objects.order_by("-captured_at")
    return render(request, "attendance/unknown_faces.html", {
        "faces": faces,
        "total_unknown_faces": faces.count(),
        "captured_today": UnknownFace.objects.filter(captured_at__date=localdate()).count(),
        "registered_face_profiles": StudentFaceData.objects.exclude(encoding__isnull=True).count(),
    })


def _extract_unknown_face_encoding(face):
    """Extract face encoding from unknown face record."""
    if face_recognition is None:
        return None, "face_recognition dependency is missing."
    if not face.image:
        return None, "No image is attached to this unknown face record."
    try:
        image = face_recognition.load_image_file(face.image.path)
    except Exception:
        LOGGER.exception("Unable to load unknown face image for face_id=%s", face.id)
        return None, "Unable to read the captured image file."
    encodings = face_recognition.face_encodings(image)
    if not encodings:
        return None, "No clear face was detected in this image."
    return encodings[0], None


def _build_image_content(image_bytes, name_prefix, extension):
    """Build Django ContentFile from image bytes."""
    safe_extension = (extension or ".jpg").lower()
    if safe_extension not in (".jpg", ".jpeg", ".png"):
        safe_extension = ".jpg"
    file_name = f"{name_prefix}_{uuid.uuid4().hex}{safe_extension}"
    return ContentFile(image_bytes, name=file_name)


@login_required
@user_passes_test(is_admin_user)
def convert_unknown_to_student(request, face_id):
    """Convert an unknown face to a student or assign to existing student."""
    face = get_object_or_404(UnknownFace, id=face_id)
    show_new_student_form = False

    if request.method == "POST":
        form = ConvertUnknownForm(request.POST, request.FILES)
        show_new_student_form = form.data.get("student_choice") == ConvertUnknownForm.ADD_NEW_SENTINEL

        if form.is_valid():
            encoding, encoding_error = _extract_unknown_face_encoding(face)
            if encoding_error:
                messages.error(request, encoding_error)
            else:
                return _process_unknown_face_conversion(request, form, face, encoding)

    else:
        form = ConvertUnknownForm()

    return render(request, "attendance/convert_unknown.html", {
        "form": form, "face": face, "show_new_student_form": show_new_student_form,
        "add_new_value": ConvertUnknownForm.ADD_NEW_SENTINEL,
    })


def _process_unknown_face_conversion(request, form, face, encoding):
    """Process unknown face conversion to student."""
    face_image_bytes = b""
    face_image_extension = ".jpg"
    if face.image:
        face_image_extension = os.path.splitext(face.image.name)[1] or ".jpg"
        try:
            with face.image.open("rb") as image_file:
                face_image_bytes = image_file.read()
        except Exception:
            LOGGER.exception("Unable to read unknown face image bytes for face_id=%s", face.id)

    try:
        with transaction.atomic():
            if form.cleaned_data.get("create_new_student"):
                full_name = form.cleaned_data["full_name"]
                roll_number = form.cleaned_data["roll_number"]
                class_name = form.cleaned_data["class_name"]
                parent_phone = form.cleaned_data["parent_phone"]
                parent_email = form.cleaned_data["parent_email"] or None

                username = build_student_username(full_name, roll_number)
                first_name, last_name = split_full_name(full_name)

                user = CustomUser.objects.create_user(
                    username=username, password=DEFAULT_PASSWORD, role="STUDENT",
                    first_name=first_name, last_name=last_name,
                )

                student = Student.objects.create(
                    user=user, full_name=full_name, roll_number=roll_number, class_name=class_name,
                    admission_date=localdate(), admission_class=Classroom.objects.filter(name=class_name).first(),
                    phone=parent_phone, parent_email=parent_email,
                )

                provided_image = form.cleaned_data.get("student_image")
                if provided_image:
                    student.image = provided_image
                    student.save(update_fields=["image"])
                elif face_image_bytes:
                    student.image.save(
                        _build_image_content(face_image_bytes, f"student_profile_{student.id}", face_image_extension).name,
                        _build_image_content(face_image_bytes, f"student_profile_{student.id}", face_image_extension),
                        save=True
                    )

                success_message = f"New student created. Username: {username} | Password: {DEFAULT_PASSWORD}"
            else:
                student = form.cleaned_data["student"]
                success_message = f"Unknown face assigned to {student.user.get_full_name() or student.user.username}."

            # Create face profile
            face_profile, _ = StudentFaceData.objects.get_or_create(student=student)
            face_profile.set_encoding(encoding)

            if face_image_bytes:
                face_image_content = _build_image_content(face_image_bytes, f"student_face_{student.id}", face_image_extension)
                face_profile.image.save(face_image_content.name, face_image_content, save=False)

            face_profile.save()

            if face.image:
                face.image.delete(save=False)
            face.delete()

        messages.success(request, success_message)
        return redirect("unknown_faces_list")

    except Exception:
        LOGGER.exception("Failed converting unknown face face_id=%s", face.id)
        messages.error(request, "Unable to complete conversion right now. Please try again.")


@login_required
@user_passes_test(is_admin_user)
@require_POST
def delete_unknown_face(request, face_id):
    """Delete an unknown face record."""
    face = get_object_or_404(UnknownFace, id=face_id)
    if face.image:
        face.image.delete(save=False)
    face.delete()
    messages.success(request, "Unknown face record deleted.")
    return redirect("unknown_faces_list")


# =====================================================
# LIVE ATTENDANCE PAGE
# =====================================================

@login_required
@user_passes_test(is_admin_user)
def live_attendance_page(request):
    """Display live attendance monitoring page."""
    cameras = ClassroomCamera.objects.order_by("class_name", "camera_index")
    return render(request, "attendance/live_attendance.html", {
        "cameras": cameras,
        "today_present_count": Attendance.objects.filter(date=localdate(), status="Present").count(),
        "unknown_faces_today": UnknownFace.objects.filter(captured_at__date=localdate()).count(),
        "face_profile_count": StudentFaceData.objects.exclude(encoding__isnull=True).count(),
        "active_camera_count": cameras.count() or 1,
        "recent_events": list(LIVE_MESSAGES),
    })


@login_required
@user_passes_test(is_admin_user)
def test_email(request):
    """Test email sending functionality."""
    send_attendance_email(student_email="youremail@gmail.com", student_name="Test Student", status="Present")
    return HttpResponse("Email Sent")


# =====================================================
# EDIT ATTENDANCE
# =====================================================

@login_required
def edit_attendance(request, id):
    """Edit an existing attendance record."""
    attendance = get_object_or_404(Attendance, id=id)

    if hasattr(request.user, "student"):
        messages.error(request, "You are not allowed to edit attendance.")
        return redirect("attendance_report")

    if hasattr(request.user, "teacher"):
        class_names = list(request.user.teacher.classes.values_list("name", flat=True))
        if attendance.student.class_name not in class_names:
            messages.error(request, "You cannot modify attendance for this class.")
            return redirect("attendance_report")

    if request.method == "POST":
        status = request.POST.get("status")
        attendance.status = status
        attendance.save()
        return redirect("attendance_report")

    return render(request, "attendance/edit_attendance.html", {"attendance": attendance})
