// lib/store.ts — global job state with Zustand
import { create } from 'zustand';
import { Lead, PipelineEvent } from './api';

export type NodeStatus = 'idle' | 'active' | 'done' | 'error';

export interface PipelineNode {
  id:     string;
  label:  string;
  status: NodeStatus;
  detail: string;
}

const NODES: PipelineNode[] = [
  { id: 'parse_query',     label: 'Query Parser',   status: 'idle', detail: 'Waiting…' },
  { id: 'scrape_maps',     label: 'Maps Scraper',   status: 'idle', detail: 'Waiting…' },
  { id: 'enrich_websites', label: 'Email Enricher', status: 'idle', detail: 'Waiting…' },
  { id: 'verify_emails',   label: 'Verifier',       status: 'idle', detail: 'Waiting…' },
  { id: 'score_leads',     label: 'Lead Scorer',    status: 'idle', detail: 'Waiting…' },
  { id: 'deliver',         label: 'Delivery',       status: 'idle', detail: 'Waiting…' },
];

interface JobStore {
  jobId:      string | null;
  jobStatus:  'idle' | 'queued' | 'running' | 'done' | 'failed';
  nodes:      PipelineNode[];
  events:     PipelineEvent[];
  leads:      Lead[];
  leadCount:  number;
  csvUrl:     string;
  xlsxUrl:    string;
  query:      string;

  setQuery:     (q: string) => void;
  startJob:     (jobId: string) => void;
  handleEvent:  (ev: PipelineEvent) => void;
  reset:        () => void;
}

export const useJobStore = create<JobStore>((set, get) => ({
  jobId:     null,
  jobStatus: 'idle',
  nodes:     NODES.map(n => ({ ...n })),
  events:    [],
  leads:     [],
  leadCount: 0,
  csvUrl:    '',
  xlsxUrl:   '',
  query:     '',

  setQuery: (q) => set({ query: q }),

  startJob: (jobId) => set({
    jobId, jobStatus: 'queued',
    events: [], leads: [], leadCount: 0, csvUrl: '', xlsxUrl: '',
    nodes: NODES.map((n, i) => ({ ...n, status: i === 0 ? 'active' : 'idle', detail: 'Waiting…' })),
  }),

  handleEvent: (ev) => {
    const nodeIds = NODES.map(n => n.id);

    set(s => {
      const nodes = s.nodes.map(n => ({ ...n }));
      let leads   = s.leads;
      let csvUrl  = s.csvUrl;
      let xlsxUrl = s.xlsxUrl;
      let leadCount = s.leadCount;
      let jobStatus = s.jobStatus as JobStore['jobStatus'];

      const advance = (nodeId: string, detail: string, status: NodeStatus = 'done') => {
        const idx = nodes.findIndex(n => n.id === nodeId);
        if (idx !== -1) {
          nodes[idx].status = status;
          nodes[idx].detail = detail;
          if (idx + 1 < nodes.length && status === 'done') {
            nodes[idx + 1].status = 'active';
          }
        }
      };

      switch (ev.node) {
        case 'start':
          jobStatus = 'running';
          break;
        case 'parse_query':
          advance('parse_query', `${ev.business_type} · ${ev.location}`);
          break;
        case 'scrape_maps':
          advance('scrape_maps', `${ev.count} businesses`);
          break;
        case 'enrich_websites':
          advance('enrich_websites', `${ev.count} with email`);
          break;
        case 'verify_emails':
          advance('verify_emails', `${ev.verified}/${ev.total} valid`);
          break;
        case 'score_leads':
          advance('score_leads', `${ev.high_quality} high-quality`);
          if (ev.preview) leads = ev.preview as Lead[];
          break;
        case 'deliver':
          advance('deliver', 'Files ready');
          csvUrl  = ev.csv_url  || '';
          xlsxUrl = ev.xlsx_url || '';
          break;
        case 'done':
          jobStatus = 'done';
          leadCount = ev.lead_count || leads.length;
          break;
        case 'fail':
          jobStatus = 'failed';
          const activeNode = nodes.find(n => n.status === 'active');
          if (activeNode) { activeNode.status = 'error'; activeNode.detail = 'Failed'; }
          break;
      }

      return {
        nodes, leads, csvUrl, xlsxUrl, leadCount, jobStatus,
        events: [...s.events, ev],
      };
    });
  },

  reset: () => set({
    jobId: null, jobStatus: 'idle',
    nodes: NODES.map(n => ({ ...n })),
    events: [], leads: [], leadCount: 0, csvUrl: '', xlsxUrl: '',
  }),
}));