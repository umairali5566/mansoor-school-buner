# SAAMS Design System & UI Blueprint

## Overview
The School Management System (SAAMS) design system provides a modern, SaaS-style interface for managing educational operations. This comprehensive guide outlines the visual identity, component library, and implementation patterns for building consistent, accessible, and premium user experiences.

## 1. Brand & Visual Identity

### Color Palette

#### Primary Colors (Semantic Tokens)
```css
:root {
  /* Brand Primary */
  --primary-50: #eef2ff;
  --primary-100: #e0e7ff;
  --primary-200: #c7d2fe;
  --primary-300: #a5b4fc;
  --primary-400: #818cf8;
  --primary-500: #6366f1;  /* primary */
  --primary-600: #4f46e5;
  --primary-700: #4338ca;
  --primary-800: #3730a3;
  --primary-900: #312e81;

  /* Accent Colors */
  --accent-cyan: #06b6d4;   /* accent */
  --accent-emerald: #10b981; /* success */
  --accent-amber: #f59e0b;  /* warning */
  --accent-rose: #f43f5e;   /* danger */
  --accent-violet: #8b5cf6; /* purple */

  /* Neutral Colors */
  --neutral-50: #f9fafb;   /* background */
  --neutral-100: #f3f4f6;
  --neutral-200: #e5e7eb;  /* card */
  --neutral-300: #d1d5db;
  --neutral-400: #9ca3af;
  --neutral-500: #6b7280;
  --neutral-600: #4b5563;  /* text-secondary */
  --neutral-700: #374151; /* text-primary */
  --neutral-800: #1f2937;
  --neutral-900: #111827;
}
```

#### Dark Mode Variants
```css
/* Dark Theme */
--primary-dark: #0F172A;    /* primary */
--secondary-dark: #1E293B;  /* secondary */
--background-dark: #0F172A; /* background */
--card-dark: rgba(255, 255, 255, 0.08); /* card */
--text-primary-dark: #ffffff; /* text-primary */
--text-secondary-dark: rgba(255, 255, 255, 0.8); /* text-secondary */
```

#### Light Mode (Default)
```css
/* Light Theme */
--primary-light: #6366f1;   /* primary */
--secondary-light: #e5e7eb; /* secondary */
--background-light: #f8fafc; /* background */
--card-light: #ffffff;     /* card */
--text-primary-light: #111827; /* text-primary */
--text-secondary-light: #6b7280; /* text-secondary */
```

### Typography

#### Font Stack
- **Primary**: Inter (400, 500, 600, 700, 800)
- **Secondary**: Poppins (500, 600, 700, 800)
- **Fallback**: system-ui, -apple-system, sans-serif

#### Hierarchy
```css
/* Headings */
h1 { font-family: 'Poppins'; font-size: 2.25rem; font-weight: 700; line-height: 1.2; }
h2 { font-family: 'Poppins'; font-size: 1.875rem; font-weight: 600; line-height: 1.3; }
h3 { font-family: 'Poppins'; font-size: 1.5rem; font-weight: 600; line-height: 1.4; }
h4 { font-family: 'Poppins'; font-size: 1.25rem; font-weight: 600; line-height: 1.4; }
h5 { font-family: 'Poppins'; font-size: 1.125rem; font-weight: 600; line-height: 1.5; }

/* Body Text */
body { font-family: 'Inter'; font-size: 1rem; font-weight: 400; line-height: 1.6; }
.small { font-size: 0.875rem; line-height: 1.5; }
.xs { font-size: 0.75rem; line-height: 1.5; }
```

#### Responsive Scaling
- Mobile: 0.875rem base
- Tablet: 1rem base
- Desktop: 1rem base
- Large: 1.125rem base

### Iconography

#### Icon Set
- **Primary**: Bootstrap Icons (bi-*)
- **Style**: Outline and filled variants
- **Sizes**: 16px, 20px, 24px, 32px, 48px
- **Usage**: Semantic mapping to actions

#### Icon Guidelines
- Use filled icons for primary actions
- Outline icons for secondary elements
- 24px default size for buttons
- 16px for form labels and small UI elements

### Style Guide

#### Images & Illustrations
- **Logo**: SVG format, scalable
- **Icons**: SVG or icon fonts
- **Photos**: 16:9 aspect ratio, 1920px minimum width
- **Illustrations**: Custom SVG, consistent with brand colors

#### Brand Assets
- **Favicon**: 32x32px, 16x16px variants
- **App Icons**: iOS (180x180px), Android (512x512px)
- **Splash Screen**: 2048x2732px for iOS, adaptive for Android

## 2. Interaction & Motion

### Animation Timings
```css
:root {
  --transition-fast: 150ms ease;     /* Hover states */
  --transition-base: 250ms ease;     /* Component transitions */
  --transition-slow: 350ms ease;     /* Page transitions */
  --transition-bounce: 400ms cubic-bezier(0.34, 1.56, 0.64, 1);
}
```

### Focus States
- **Color**: Primary blue (#6366f1) outline
- **Width**: 2px solid outline
- **Offset**: 2px from element
- **Radius**: Matches element border-radius

### Loading States
```css
/* Spinner */
.loading-spinner {
  width: 20px;
  height: 20px;
  border: 2px solid var(--neutral-200);
  border-top: 2px solid var(--primary-500);
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  0% { transform: rotate(0deg); }
  100% { transform: rotate(360deg); }
}
```

### Modal Transitions
- **Entrance**: Scale in from 95% with fade
- **Exit**: Scale out to 105% with fade
- **Backdrop**: Blur effect with fade
- **Duration**: 250ms ease-out

## 3. Layout & Navigation

### Sidebar Navigation
```css
.sidebar {
  width: 256px;                    /* w-64 */
  background: var(--primary-dark);
  border-right: 1px solid #374151;
  position: fixed;
  height: 100vh;
  z-index: 40;
}

.sidebar-nav {
  padding: 1.5rem 1.5rem;
}

.nav-item {
  padding: 0.75rem 1rem;
  border-radius: 0.75rem;
  margin-bottom: 0.25rem;
  transition: all 300ms ease;
}

.nav-item:hover {
  background: rgba(255, 255, 255, 0.1);
}

.nav-item.active {
  background: linear-gradient(135deg, #3B82F6, #8B5CF6);
  box-shadow: 0 4px 12px rgba(99, 102, 241, 0.3);
}
```

#### Responsive Behavior
- Desktop: Fixed sidebar
- Tablet: Collapsible sidebar
- Mobile: Overlay sidebar with hamburger menu

### Topbar
```css
.navbar {
  background: #ffffff;
  border-bottom: 1px solid #e5e7eb;
  padding: 1.5rem 2rem;
  position: sticky;
  top: 0;
  z-index: 30;
}

.search-input {
  padding-left: 2.5rem;
  padding-right: 1rem;
  padding-top: 0.5rem;
  padding-bottom: 0.5rem;
  background: #ffffff;
  border: 1px solid #d1d5db;
  border-radius: 0.5rem;
}

.notification-badge {
  position: absolute;
  top: -0.25rem;
  right: -0.25rem;
  width: 0.75rem;
  height: 0.75rem;
  background: #ef4444;
  border-radius: 9999px;
}
```

### Grid System
- **Desktop**: 12-column fluid grid
- **Tablet**: 2-column stack
- **Mobile**: Single column stack

### Card System
```css
.card {
  background: #ffffff;
  border: 1px solid #e5e7eb;
  border-radius: 0.75rem;  /* 12-16px */
  box-shadow: 0 1px 3px rgba(0, 0, 0, 0.1);
  transition: all 200ms ease;
}

.card:hover {
  transform: translateY(-2px);
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
}

.card-padding {
  padding: 1.5rem;
}

.card-margin {
  margin-bottom: 1.5rem;
}
```

## 4. Component Library

### Form Elements

#### Text Input
```jsx
// JSX/React Example
const TextInput = ({ label, placeholder, type = 'text', error, ...props }) => (
  <div className="field">
    <label className="form-label">{label}</label>
    <div className="input-shell">
      <input
        type={type}
        className="form-input"
        placeholder={placeholder}
        {...props}
      />
    </div>
    {error && <div className="field-error">{error}</div>}
  </div>
);

// States
// - Default: border-neutral-300
// - Focus: border-primary-500, ring-primary-200
// - Error: border-danger-500
// - Disabled: opacity-50, cursor-not-allowed
```

#### Password Field with Toggle
```jsx
const PasswordInput = ({ label, placeholder, error, ...props }) => {
  const [showPassword, setShowPassword] = useState(false);

  return (
    <div className="field">
      <label className="form-label">{label}</label>
      <div className="input-shell">
        <input
          type={showPassword ? 'text' : 'password'}
          className="form-input"
          placeholder={placeholder}
          {...props}
        />
        <button
          type="button"
          className="pw-toggle"
          onClick={() => setShowPassword(!showPassword)}
          aria-label={showPassword ? 'Hide password' : 'Show password'}
        >
          {/* Icon */}
        </button>
      </div>
      {error && <div className="field-error">{error}</div>}
    </div>
  );
};
```

#### Role Selector (Radio/Toggle)
```jsx
const RoleSelector = ({ options, selected, onChange }) => (
  <div className="role-select">
    <p className="role-select-label">Login as:</p>
    <div className="role-cards">
      {options.map(option => (
        <button
          key={option.value}
          type="button"
          className={`role-card ${selected === option.value ? 'selected' : ''}`}
          onClick={() => onChange(option.value)}
        >
          <span className="role-icon">{option.icon}</span>
          <span className="role-name">{option.label}</span>
        </button>
      ))}
    </div>
  </div>
);
```

### Buttons

#### Primary Button
```jsx
const Button = ({
  children,
  variant = 'primary',
  size = 'md',
  loading = false,
  disabled = false,
  ...props
}) => {
  const baseClasses = 'btn-modern font-semibold rounded-lg transition-all duration-200';
  const variants = {
    primary: 'btn-modern-primary',
    secondary: 'bg-gray-200 text-gray-900 hover:bg-gray-300',
    destructive: 'bg-red-600 text-white hover:bg-red-700'
  };

  return (
    <button
      className={`${baseClasses} ${variants[variant]} ${loading ? 'opacity-50 cursor-not-allowed' : ''}`}
      disabled={disabled || loading}
      {...props}
    >
      {loading && <LoadingSpinner />}
      {children}
    </button>
  );
};

// States:
// - Default: gradient background
// - Hover: translateY(-2px), enhanced shadow
// - Active: translateY(0), pressed effect
// - Disabled: opacity-50, no interactions
// - Loading: spinner + disabled state
```

### Cards

#### Statistic Card
```jsx
const StatCard = ({ icon, title, value, change, trend }) => (
  <div className="saas-stat-card">
    <div className="saas-stat-main">
      <div className="saas-stat-icon">
        <i className={icon}></i>
      </div>
      <div>
        <div className="saas-stat-label">{title}</div>
        <div className="saas-stat-value">{value}</div>
      </div>
    </div>
    {change && (
      <div className="saas-stat-footer">
        <span className={`text-sm ${trend === 'up' ? 'text-green-600' : 'text-red-600'}`}>
          {change}
        </span>
      </div>
    )}
  </div>
);
```

#### Activity Card
```jsx
const ActivityCard = ({ title, timestamp, description, status }) => (
  <div className="activity-card">
    <div className="activity-header">
      <h4>{title}</h4>
      <span className="activity-time">{timestamp}</span>
    </div>
    <p className="activity-description">{description}</p>
    <div className={`status-badge status-${status}`}>
      {status}
    </div>
  </div>
);
```

#### Alert Card
```jsx
const AlertCard = ({ type, title, message, dismissible = false, onDismiss }) => (
  <div className={`dashboard-alert dashboard-alert-${type}`}>
    <div className="alert-icon">
      {/* Icon based on type */}
    </div>
    <div className="alert-content">
      <h4>{title}</h4>
      <p>{message}</p>
    </div>
    {dismissible && (
      <button className="alert-dismiss" onClick={onDismiss}>
        ×
      </button>
    )}
  </div>
);
```

### Tables

#### Data Table
```jsx
const DataTable = ({ columns, data, sortable = true, selectable = false }) => {
  const [sortConfig, setSortConfig] = useState({ key: null, direction: 'asc' });
  const [selectedRows, setSelectedRows] = useState([]);

  const handleSort = (key) => {
    if (!sortable) return;
    setSortConfig(prev => ({
      key,
      direction: prev.key === key && prev.direction === 'asc' ? 'desc' : 'asc'
    }));
  };

  return (
    <div className="table-shell">
      <table className="saas-table">
        <thead>
          <tr>
            {selectable && <th><input type="checkbox" /></th>}
            {columns.map(col => (
              <th
                key={col.key}
                className={sortable ? 'sortable' : ''}
                onClick={() => handleSort(col.key)}
              >
                {col.label}
                {sortConfig.key === col.key && (
                  <i className={`bi bi-chevron-${sortConfig.direction === 'asc' ? 'up' : 'down'}`}></i>
                )}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {data.map(row => (
            <tr key={row.id} className={selectedRows.includes(row.id) ? 'selected' : ''}>
              {selectable && (
                <td>
                  <input
                    type="checkbox"
                    checked={selectedRows.includes(row.id)}
                    onChange={() => toggleRow(row.id)}
                  />
                </td>
              )}
              {columns.map(col => (
                <td key={col.key}>{row[col.key]}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
};
```

### Charts

#### Chart Container (Chart.js Integration)
```jsx
import { Chart as ChartJS, ArcElement, Tooltip, Legend } from 'chart.js';
import { Doughnut } from 'react-chartjs-2';

ChartJS.register(ArcElement, Tooltip, Legend);

const AttendanceChart = ({ data }) => {
  const chartData = {
    labels: ['Present', 'Absent', 'Late'],
    datasets: [{
      data: [data.present, data.absent, data.late],
      backgroundColor: [
        'rgba(16, 185, 129, 0.8)',
        'rgba(239, 68, 68, 0.8)',
        'rgba(245, 158, 11, 0.8)'
      ],
      borderWidth: 2,
      borderColor: '#ffffff'
    }]
  };

  return (
    <div className="chart-wrap">
      <Doughnut data={chartData} options={chartOptions} />
    </div>
  );
};
```

### Modals

#### Confirmation Modal
```jsx
const ConfirmationModal = ({ isOpen, onClose, onConfirm, title, message, confirmText = 'Confirm' }) => (
  <div className={`modal-overlay ${isOpen ? 'open' : ''}`} onClick={onClose}>
    <div className="modal-content" onClick={e => e.stopPropagation()}>
      <div className="modal-header">
        <h3>{title}</h3>
        <button onClick={onClose}>×</button>
      </div>
      <div className="modal-body">
        <p>{message}</p>
      </div>
      <div className="modal-footer">
        <button className="btn-secondary" onClick={onClose}>Cancel</button>
        <button className="btn-primary" onClick={onConfirm}>{confirmText}</button>
      </div>
    </div>
  </div>
);
```

#### Edit Form Modal
```jsx
const EditModal = ({ isOpen, onClose, onSave, title, children, loading = false }) => (
  <div className={`modal-overlay ${isOpen ? 'open' : ''}`} onClick={onClose}>
    <div className="modal-content large" onClick={e => e.stopPropagation()}>
      <div className="modal-header">
        <h3>{title}</h3>
        <button onClick={onClose} disabled={loading}>×</button>
      </div>
      <div className="modal-body">
        {children}
      </div>
      <div className="modal-footer">
        <button className="btn-secondary" onClick={onClose} disabled={loading}>Cancel</button>
        <button className="btn-primary" onClick={onSave} disabled={loading}>
          {loading ? 'Saving...' : 'Save Changes'}
        </button>
      </div>
    </div>
  </div>
);
```

### Dropdowns & Selects

#### Multi-Select Dropdown
```jsx
const MultiSelect = ({ options, selected, onChange, placeholder }) => {
  const [isOpen, setIsOpen] = useState(false);
  const [searchTerm, setSearchTerm] = useState('');

  const filteredOptions = options.filter(option =>
    option.label.toLowerCase().includes(searchTerm.toLowerCase())
  );

  return (
    <div className="dropdown-container">
      <div className="dropdown-trigger" onClick={() => setIsOpen(!isOpen)}>
        <span>{selected.length ? `${selected.length} selected` : placeholder}</span>
        <i className="dropdown-arrow"></i>
      </div>
      {isOpen && (
        <div className="dropdown-menu">
          <input
            type="text"
            placeholder="Search..."
            value={searchTerm}
            onChange={(e) => setSearchTerm(e.target.value)}
            className="dropdown-search"
          />
          {filteredOptions.map(option => (
            <div
              key={option.value}
              className={`dropdown-item ${selected.includes(option.value) ? 'selected' : ''}`}
              onClick={() => {
                const newSelected = selected.includes(option.value)
                  ? selected.filter(v => v !== option.value)
                  : [...selected, option.value];
                onChange(newSelected);
              }}
            >
              <input type="checkbox" checked={selected.includes(option.value)} readOnly />
              {option.label}
            </div>
          ))}
        </div>
      )}
    </div>
  );
};
```

### Tabs

#### Horizontal Tabs
```jsx
const Tabs = ({ tabs, activeTab, onChange }) => (
  <div className="tabs-container">
    <div className="tabs-header">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`tab-button ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.icon && <i className={tab.icon}></i>}
          {tab.label}
        </button>
      ))}
    </div>
    <div className="tabs-content">
      {tabs.find(tab => tab.id === activeTab)?.content}
    </div>
  </div>
);
```

#### Vertical Tabs
```jsx
const VerticalTabs = ({ tabs, activeTab, onChange }) => (
  <div className="vertical-tabs-container">
    <div className="vertical-tabs-sidebar">
      {tabs.map(tab => (
        <button
          key={tab.id}
          className={`vertical-tab-button ${activeTab === tab.id ? 'active' : ''}`}
          onClick={() => onChange(tab.id)}
        >
          {tab.icon && <i className={tab.icon}></i>}
          <span>{tab.label}</span>
        </button>
      ))}
    </div>
    <div className="vertical-tabs-content">
      {tabs.find(tab => tab.id === activeTab)?.content}
    </div>
  </div>
);
```

## 5. Page Layouts

### Login Page

#### Layout Structure
```
┌─────────────────────────────────────┐
│         Decorative Header           │
│   [Logo] SAAMS - School Management  │
├─────────────────┬───────────────────┤
│                 │                   │
│   Form Panel    │   Hero Panel      │
│                 │                   │
│   • Username    │   Welcome text    │
│   • Password    │   Description     │
│   • Remember    │   Animated shape  │
│   • Login btn   │                   │
│   • Role cards  │                   │
│                 │                   │
└─────────────────┴───────────────────┘
```

#### Responsive Behavior
- **Desktop**: Side-by-side layout (1:1 ratio)
- **Tablet**: Stacked layout (form top, hero bottom)
- **Mobile**: Single column, hero simplified

#### Component Hierarchy
```
LoginPage
├── Scene (background animations)
├── Layout
│   ├── Shell (grid container)
│   │   ├── Left (form section)
│   │   │   ├── Brand
│   │   │   ├── Messages/Alerts
│   │   │   ├── Form
│   │   │   │   ├── TextInput (username)
│   │   │   │   ├── PasswordInput
│   │   │   │   ├── Meta (remember/forgot)
│   │   │   │   └── Button (login)
│   │   │   └── RoleSelector
│   │   └── Right (hero section)
│   │       ├── Heading
│   │       ├── Description
│   │       └── Shape3D (decoration)
└── PWA Install Banner
```

### Dashboard Pages

#### Admin Dashboard Layout
```
┌─────────────────────────────────────┐
│ Topbar [Search] [Notifications] [Profile] │
├─────────────────┬───────────────────┤
│ Sidebar         │ Main Content      │
│ • Dashboard     │                   │
│ • Students      │ Hero Section      │
│ • Teachers      │ [Stats Grid]      │
│ • Admissions    │                   │
│ • Reports       │ Action Cards      │
│ • Live Attend.  │ [4-column grid]   │
│ • Settings      │                   │
│                 │ Charts Section    │
│                 │ [2-column grid]   │
│                 │                   │
│                 │ Advanced Section  │
│                 │ [2-column grid]   │
└─────────────────┴───────────────────┘
```

#### Teacher Dashboard Layout
```
TeacherDashboard
├── Sidebar (role-specific nav)
├── MainContent
│   ├── HeroSection
│   │   ├── WelcomeMessage
│   │   └── QuickStats
│   ├── ClassList
│   │   └── ClassCard[]
│   ├── AttendanceSection
│   │   ├── MarkAttendanceButton
│   │   └── RecentAttendanceTable
│   ├── HomeworkSection
│   │   ├── UploadHomeworkButton
│   │   └── HomeworkListTable
│   └── ResultsSection
│       ├── AddResultButton
│       └── ResultsTable
```

#### Student Dashboard Layout
```
StudentDashboard
├── Sidebar (student nav)
├── MainContent
│   ├── ProfileCard
│   │   ├── Avatar
│   │   ├── Info
│   │   └── QuickStats
│   ├── ActivityFeed
│   │   └── ActivityCard[]
│   ├── AttendanceChart
│   ├── HomeworkList
│   └── ResultsGraph
```

## 6. Data Flow & State Management

### Data Structures

#### Student Model
```typescript
interface Student {
  id: number;
  user: User;
  roll_number: string;
  class: Class;
  section: string;
  admission_date: Date;
  image?: string;
  attendance_percentage: number;
  contact_info: {
    phone: string;
    email: string;
    address: string;
  };
}
```

#### Attendance Record
```typescript
interface Attendance {
  id: number;
  student: Student;
  date: Date;
  status: 'present' | 'absent' | 'late';
  marked_by: Teacher;
  timestamp: Date;
  location?: string;
  face_recognized: boolean;
}
```

#### Homework
```typescript
interface Homework {
  id: number;
  title: string;
  description: string;
  class: Class;
  subject: string;
  due_date: Date;
  file?: string;
  created_by: Teacher;
  submissions: HomeworkSubmission[];
}
```

### API Endpoints

#### REST API Structure
```
GET    /api/students/           # List students
POST   /api/students/           # Create student
GET    /api/students/{id}/      # Get student details
PUT    /api/students/{id}/      # Update student
DELETE /api/students/{id}/      # Delete student

GET    /api/attendance/         # Attendance records
POST   /api/attendance/mark/    # Mark attendance
GET    /api/attendance/report/  # Generate report

GET    /api/homework/           # Homework list
POST   /api/homework/           # Create homework
GET    /api/homework/{id}/submissions/  # Get submissions
```

#### Response Format
```json
{
  "success": true,
  "data": { ... },
  "message": "Operation successful",
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 150
  }
}
```

### State Management (Zustand)

#### Store Structure
```typescript
// stores/auth.ts
interface AuthState {
  user: User | null;
  role: 'admin' | 'teacher' | 'student' | null;
  isAuthenticated: boolean;
  login: (credentials) => Promise<void>;
  logout: () => void;
}

// stores/students.ts
interface StudentsState {
  students: Student[];
  loading: boolean;
  fetchStudents: () => Promise<void>;
  addStudent: (student) => Promise<void>;
  updateStudent: (id, data) => Promise<void>;
}

// stores/attendance.ts
interface AttendanceState {
  records: Attendance[];
  stats: AttendanceStats;
  markAttendance: (data) => Promise<void>;
  fetchStats: () => Promise<void>;
}
```

## 7. Accessibility & SEO

### WCAG 2.1 AA Compliance

#### Color Contrast
- Normal text: 4.5:1 minimum
- Large text: 3:1 minimum
- UI components: 3:1 minimum

#### Focus Management
```css
/* Focus ring */
.focus-ring {
  outline: 2px solid #6366f1;
  outline-offset: 2px;
}

/* Focus visible only on keyboard navigation */
.focus-visible:focus-visible {
  outline: 2px solid #6366f1;
  outline-offset: 2px;
}
```

#### ARIA Attributes
```jsx
// Modal
<div role="dialog" aria-labelledby="modal-title" aria-describedby="modal-description">
  <h2 id="modal-title">Confirm Action</h2>
  <p id="modal-description">Are you sure you want to delete this item?</p>
  <button aria-label="Close modal">×</button>
</div>

// Form
<form aria-labelledby="form-title">
  <fieldset>
    <legend id="form-title">User Information</legend>
    <label for="username">Username</label>
    <input id="username" aria-describedby="username-help" />
    <div id="username-help">Enter your preferred username</div>
  </fieldset>
</form>
```

#### Semantic HTML
- Use proper heading hierarchy (h1-h6)
- Semantic form elements
- ARIA landmarks (banner, navigation, main, complementary)
- Screen reader friendly tables with scope attributes

### SEO Best Practices

#### SPA Routing
```javascript
// React Router with history API
import { BrowserRouter, Routes, Route } from 'react-router-dom';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/dashboard" element={<Dashboard />} />
        <Route path="/students" element={<Students />} />
      </Routes>
    </BrowserRouter>
  );
}
```

#### Meta Tags
```html
<!-- Base meta tags -->
<meta name="description" content="Modern school management system for efficient administration">
<meta name="keywords" content="school management, attendance, students, teachers">
<meta name="author" content="SAAMS Team">

<!-- Open Graph -->
<meta property="og:title" content="SAAMS - School Management System">
<meta property="og:description" content="Comprehensive school management solution">
<meta property="og:image" content="/og-image.png">
<meta property="og:url" content="https://saams.edu">

<!-- Twitter Cards -->
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="SAAMS">
<meta name="twitter:description" content="Modern school management system">
```

#### Structured Data
```json
{
  "@context": "https://schema.org",
  "@type": "WebApplication",
  "name": "SAAMS",
  "description": "School Management System",
  "url": "https://saams.edu",
  "applicationCategory": "BusinessApplication",
  "operatingSystem": "Web Browser",
  "offers": {
    "@type": "Offer",
    "price": "0",
    "priceCurrency": "USD"
  }
}
```

## 8. Documentation & Deliverables

### Figma Design System
- **Components Library**: All UI components with variants
- **Design Tokens**: Colors, typography, spacing
- **Page Templates**: Login, dashboards, forms
- **Interactive Prototypes**: Hover states, transitions
- **Responsive Breakpoints**: Mobile, tablet, desktop

### Storybook Component Library
```javascript
// .storybook/main.js
module.exports = {
  stories: ['../src/**/*.stories.mdx', '../src/**/*.stories.@(js|jsx|ts|tsx)'],
  addons: ['@storybook/addon-essentials', '@storybook/addon-a11y'],
  framework: '@storybook/react'
};
```

#### Component Stories
```jsx
// components/Button.stories.jsx
import { Button } from './Button';

export default {
  title: 'Components/Button',
  component: Button,
  parameters: {
    docs: {
      description: {
        component: 'Primary button component with multiple variants.'
      }
    }
  }
};

const Template = (args) => <Button {...args} />;

export const Primary = Template.bind({});
Primary.args = {
  children: 'Click me',
  variant: 'primary'
};

export const Secondary = Template.bind({});
Secondary.args = {
  children: 'Click me',
  variant: 'secondary'
};
```

### README Documentation
```markdown
# SAAMS Design System

A comprehensive design system for the School Management System.

## Installation

```bash
npm install @saams/design-system
```

## Usage

```jsx
import { Button, Card, TextInput } from '@saams/design-system';

function App() {
  return (
    <div>
      <Button variant="primary">Click me</Button>
      <Card title="Student Info">
        <TextInput label="Name" placeholder="Enter student name" />
      </Card>
    </div>
  );
}
```

## Development

### Setup
```bash
git clone https://github.com/saams/design-system.git
cd design-system
npm install
```

### Storybook
```bash
npm run storybook
```

### Build
```bash
npm run build
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests and stories
5. Submit a pull request

## License

MIT License - see LICENSE file for details.
```

### Future Proofing Strategy

#### Theme System
```typescript
// Theme configuration
interface Theme {
  colors: {
    primary: string;
    secondary: string;
    background: string;
    // ... more colors
  };
  typography: {
    fontFamily: string;
    fontSize: { ... };
  };
  spacing: { ... };
  breakpoints: { ... };
}

// Theme switching
const themes = {
  light: { ... },
  dark: { ... },
  highContrast: { ... }
};

const ThemeProvider = ({ theme, children }) => (
  <div style={{ '--theme-primary': theme.colors.primary }}>
    {children}
  </div>
);
```

#### Component API Evolution
- Semantic versioning for components
- Deprecation warnings for breaking changes
- Migration guides for major updates
- Backwards compatibility layers

#### Scalability Considerations
- Design token system for easy theming
- Component composition over inheritance
- Performance optimization (lazy loading, tree shaking)
- Internationalization support

This design system provides a solid foundation for SAAMS, ensuring consistency, accessibility, and maintainability across all user interfaces. The modular approach allows for easy updates and extensions as the system grows.