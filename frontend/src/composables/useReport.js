import { ref, computed } from 'vue';

export function useReport() {
  const currentReport = ref(null);

  const setReport = (reportData) => {
    currentReport.value = reportData;
  };

  const hasReport = computed(() => !!currentReport.value);

  return {
    currentReport,
    setReport,
    hasReport
  };
}
