import { useState, useEffect } from 'react';
import { CodingMetrics } from '../types/metrics';
import { metricsService } from '../services/metricsService';

export const useCodingMetrics = () => {
  const [metrics, setMetrics] = useState<CodingMetrics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const fetchMetrics = async () => {
      try {
        setLoading(true);
        const data = await metricsService.getCodingMetrics();
        setMetrics(data);
        setError(null);
      } catch (err) {
        setError(err instanceof Error ? err.message : 'Failed to fetch metrics');
      } finally {
        setLoading(false);
      }
    };

    fetchMetrics();
    
    // Refresh metrics every 5 minutes
    const interval = setInterval(fetchMetrics, 5 * 60 * 1000);
    
    return () => clearInterval(interval);
  }, []);

  const refreshMetrics = async () => {
    try {
      setLoading(true);
      const data = await metricsService.getCodingMetrics();
      setMetrics(data);
      setError(null);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to refresh metrics');
    } finally {
      setLoading(false);
    }
  };

  return {
    metrics,
    loading,
    error,
    refreshMetrics
  };
};