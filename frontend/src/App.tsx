import { Navigate, Route, Routes } from 'react-router-dom';

import { AppShell } from '@/components/layout/AppShell';
import { ThemeProvider } from '@/components/layout/ThemeProvider';
import { AboutRoute } from '@/routes/AboutRoute';
import { AnalyzeRoute } from '@/routes/AnalyzeRoute';
import { NotFoundRoute } from '@/routes/NotFoundRoute';
import { ScanRoute } from '@/routes/ScanRoute';

export function App() {
  return (
    <ThemeProvider>
      <AppShell>
        <Routes>
          <Route path="/" element={<AnalyzeRoute />} />
          <Route path="/scan/:scanId" element={<ScanRoute />} />
          <Route path="/scan/:scanId/:sectionKey" element={<ScanRoute />} />
          <Route path="/about" element={<AboutRoute />} />
          <Route path="/index.html" element={<Navigate to="/" replace />} />
          <Route path="*" element={<NotFoundRoute />} />
        </Routes>
      </AppShell>
    </ThemeProvider>
  );
}
