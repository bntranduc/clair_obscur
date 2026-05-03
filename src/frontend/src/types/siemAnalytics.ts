export type SiemKeyCount = { key: string; count: number };

export type SiemTimelinePoint = { t: string; count: number };

export type SiemTopIp = { ip: string; count: number };

/** Point issu d’un log disposant de ``geolocation_lat`` / ``geolocation_lon``. */
export type SiemGeoLogPoint = {
  lat: number;
  lon: number;
  timestamp?: string;
  source_ip?: string;
  log_source?: string;
  geolocation_country?: string;
};

export type SiemDashboard = {
  generated_at: string;
  time_range_hours: number;
  total_events: number;
  events_per_minute_avg: number;
  unique_source_ips: number;
  timeline: SiemTimelinePoint[];
  log_sources: SiemKeyCount[];
  protocols: SiemKeyCount[];
  network_actions: SiemKeyCount[];
  auth_by_status: SiemKeyCount[];
  top_source_ips: SiemTopIp[];
  system_by_severity: SiemKeyCount[];
  /** Échantillon de logs géolocalisés (OpenSearch ou démo). */
  geo_logs: SiemGeoLogPoint[];
  data_source: "opensearch" | "demo";
};
