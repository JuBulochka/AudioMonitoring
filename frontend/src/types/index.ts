// ═══════════════════════════════════════════════════
// Auth
// ═══════════════════════════════════════════════════

export interface AuthTokens {
  access: string;
  refresh: string;
}

export interface UserProfile {
  id: number;
  username: string;
  email: string;
  full_name: string;
  role: 'admin' | 'supervisor' | 'operator' | 'viewer';
  role_display: string;
  is_active: boolean;
}

// ═══════════════════════════════════════════════════
// Devices
// ═══════════════════════════════════════════════════

export type DeviceStatus =
  | 'normal'
  | 'needs_inspection'
  | 'needs_reconfiguration'
  | 'site_visit_required'
  | 'in_progress'
  | 'resolved'
  | 'false_positive'
  | 'offline';

export interface Device {
  id: string;
  serial_number: string;
  name: string;
  status: DeviceStatus;
  status_display: string;
  is_online: boolean;
  is_active: boolean;
  last_seen_at: string | null;
  last_packet_at: string | null;
  firmware_version: string;
  model_version: string;
  tunnel_port: number | null;
  latitude: number;
  longitude: number;
  region_name: string;
  field_name: string;
  site_name: string;
  well_number: string;
  assigned_operator_name: string | null;
  tags: string[];
  notes: string;
  created_at: string;
}

export interface DeviceHeartbeat {
  id: number;
  received_at: string;
  cpu_temp: number | null;
  cpu_usage: number | null;
  memory_total_mb: number | null;
  memory_used_mb: number | null;
  disk_total_gb: number | null;
  disk_used_gb: number | null;
  firmware_version: string;
  model_version: string;
  uptime_seconds: number | null;
  disk_usage_pct: number | null;
  memory_usage_pct: number | null;
}

// ═══════════════════════════════════════════════════
// Audio Packets
// ═══════════════════════════════════════════════════

export type SeverityLevel = 'info' | 'warning' | 'critical';
export type OperatorStatus = 'pending' | 'reviewed' | 'false_positive' | 'escalated';

export interface ClassScore {
  audio_class: string;
  score: number;
  threshold_exceeded: boolean;
}

export interface AudioPacket {
  id: string;
  device_id: string;
  recorded_at: string;
  severity: SeverityLevel;
  severity_display: string;
  dominant_class: string;
  dominant_class_display: string;
  dominant_class_score: number | null;
  has_anomaly: boolean;
  duration_seconds: number | null;
  audio_file: string | null;
  audio_format: string;
  operator_status: OperatorStatus;
  class_scores: ClassScore[];
}

// ═══════════════════════════════════════════════════
// Incidents
// ═══════════════════════════════════════════════════

export type IncidentStatus = 'open' | 'acknowledged' | 'in_progress' | 'resolved' | 'closed' | 'false_positive';
export type IncidentSeverity = 'info' | 'warning' | 'critical';
export type IncidentType = 'anomaly_detected' | 'device_offline' | 'manual' | 'threshold_exceeded';

export interface Incident {
  id: string;
  title: string;
  description: string;
  status: IncidentStatus;
  status_display: string;
  severity: IncidentSeverity;
  severity_display: string;
  incident_type: IncidentType;
  incident_type_display: string;
  device: { id: string; serial_number: string; name: string };
  assigned_to: { id: number; username: string; full_name: string } | null;
  trigger_class: string | null;
  trigger_score: number | null;
  resolution_notes: string;
  comment_count: number;
  created_at: string;
  updated_at: string;
  resolved_at: string | null;
}

// ═══════════════════════════════════════════════════
// Alerts / Notifications
// ═══════════════════════════════════════════════════

export type AlertSeverity = 'info' | 'warning' | 'critical';

export interface Notification {
  id: string;
  title: string;
  message: string;
  severity: AlertSeverity;
  severity_display: string;
  is_read: boolean;
  is_dismissed: boolean;
  created_at: string;
  device: { id: string; serial_number: string } | null;
  incident: { id: string; title: string } | null;
}

// ═══════════════════════════════════════════════════
// Dashboard
// ═══════════════════════════════════════════════════

export interface DashboardSummary {
  devices: {
    total: number;
    online: number;
    offline: number;
    critical: number;
  };
  packets_24h: {
    total: number;
    anomalies: number;
    critical: number;
  };
  incidents: {
    open: number;
    critical: number;
  };
  unread_notifications: number;
  top_problem_devices: Array<{
    device__id: string;
    device__serial_number: string;
    device__name: string;
    anomaly_count: number;
  }>;
  hourly_chart: Array<{
    hour: string;
    total: number;
    anomaly: number;
  }>;
}

// ═══════════════════════════════════════════════════
// Pagination
// ═══════════════════════════════════════════════════

export interface PaginatedResponse<T> {
  count: number;
  next: string | null;
  previous: string | null;
  results: T[];
}

// ═══════════════════════════════════════════════════
// Comments
// ═══════════════════════════════════════════════════

export interface IncidentComment {
  id: string;
  text: string;
  is_system: boolean;
  author_name: string;
  created_at: string;
}

// ═══════════════════════════════════════════════════
// Commands
// ═══════════════════════════════════════════════════

export type CommandStatus = 'pending' | 'running' | 'completed' | 'failed' | 'timeout' | 'cancelled';

/** Flat item returned by GET /api/v1/commands/?device=<id> */
export interface DeviceCommandItem {
  id: string;
  command_key: string;
  label: string;
  category: string;
  icon: string;
  status: CommandStatus;
  exit_code: number | null;
  sent_by: string | null;
  created_at: string;
  picked_up_at: string | null;
  completed_at: string | null;
  duration_sec: number | null;
  has_output: boolean;
}

/** Full detail returned by GET /api/v1/commands/<id>/ */
export interface DeviceCommandDetail {
  id: string;
  command_key: string;
  label: string;
  category: string;
  description: string;
  params: Record<string, unknown>;
  status: CommandStatus;
  exit_code: number | null;
  output: string;
  error_message: string;
  sent_by: string | null;
  device: { id: string; serial: string };
  created_at: string;
  picked_up_at: string | null;
  completed_at: string | null;
  duration_sec: number | null;
}

/** Kept for backward compat — use DeviceCommandItem / DeviceCommandDetail instead */
export interface DeviceCommand {
  id: string;
  command_key: string;
  label: string;
  status: CommandStatus;
  output: string;
  exit_code: number | null;
  sent_at: string | null;
  completed_at: string | null;
  created_at: string;
}
