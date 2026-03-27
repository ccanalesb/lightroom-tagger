import { createContext, useContext, useEffect, useState, useCallback, useMemo } from 'react';
import type { ReactNode } from 'react';
import { SystemAPI } from '../services/api';
import { ADVANCED_WEIGHTS_MUST_SUM } from '../constants/strings';

interface MatchOptions {
  selectedModel: string;
  threshold: number;
  phashWeight: number;
  descWeight: number;
  visionWeight: number;
}

const DEFAULT_OPTIONS: MatchOptions = {
  selectedModel: '',
  threshold: 0.7,
  phashWeight: 0,
  descWeight: 0,
  visionWeight: 1,
};

interface MatchOptionsContextValue {
  options: MatchOptions;
  updateOption: <K extends keyof MatchOptions>(key: K, value: MatchOptions[K]) => void;
  resetOptions: () => void;
  availableModels: { name: string; default: boolean }[];
  weightsError: string | null;
}

const MatchOptionsContext = createContext<MatchOptionsContextValue | null>(null);

export function MatchOptionsProvider({ children }: { children: ReactNode }) {
  const [options, setOptions] = useState<MatchOptions>({ ...DEFAULT_OPTIONS });
  const [availableModels, setAvailableModels] = useState<{ name: string; default: boolean }[]>([]);

  useEffect(() => {
    SystemAPI.visionModels()
      .then((data) => {
        setAvailableModels(data.models);
        const defaultModel = data.models.find((m) => m.default) ?? data.models[0];
        if (defaultModel) setOptions((prev) => ({ ...prev, selectedModel: defaultModel.name }));
      })
      .catch(console.error);
  }, []);

  const updateOption = useCallback(<K extends keyof MatchOptions>(key: K, value: MatchOptions[K]) => {
    setOptions((prev) => ({ ...prev, [key]: value }));
  }, []);

  const resetOptions = useCallback(() => {
    setOptions((prev) => ({ ...DEFAULT_OPTIONS, selectedModel: prev.selectedModel }));
  }, []);

  const weightsError = useMemo(() => {
    const total = options.phashWeight + options.descWeight + options.visionWeight;
    return Math.abs(total - 1.0) >= 0.001 ? ADVANCED_WEIGHTS_MUST_SUM : null;
  }, [options.phashWeight, options.descWeight, options.visionWeight]);

  const value = useMemo(() => ({
    options,
    updateOption,
    resetOptions,
    availableModels,
    weightsError,
  }), [options, updateOption, resetOptions, availableModels, weightsError]);

  return (
    <MatchOptionsContext.Provider value={value}>
      {children}
    </MatchOptionsContext.Provider>
  );
}

export function useMatchOptions() {
  const ctx = useContext(MatchOptionsContext);
  if (!ctx) throw new Error('useMatchOptions must be used within MatchOptionsProvider');
  return ctx;
}
