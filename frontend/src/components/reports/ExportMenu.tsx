import { DownloadIcon, FileArchiveIcon, FileJson2Icon, FileTextIcon } from 'lucide-react';
import { useState } from 'react';

import { Button } from '@/components/ui/button';
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from '@/components/ui/dropdown-menu';
import { bundleToZip, downloadBlob, downloadJson, downloadText } from '@/features/reports/bundle';
import { buildReportBundle } from '@/features/reports/generate';
import { REPORT_DEFINITIONS } from '@/features/reports/markdown/renderers';
import { renderAnalysisJson } from '@/features/reports/json';
import { useStoredScreenshots } from '@/features/history/useScanLibrary';
import type { AnalysisResult } from '@/types/analysis';

/**
 * Report downloads.
 *
 * Generated in the browser from the stored result, so exports keep working after a restart with the
 * backend stopped (docs/blueprint/decisions.md D2).
 */
export function ExportMenu({ result }: { result: AnalysisResult }) {
  const screenshots = useStoredScreenshots(result.scan.scan_id);
  const [busy, setBusy] = useState(false);

  const bundle = buildReportBundle(result);

  const downloadZip = async () => {
    setBusy(true);
    try {
      const blob = await bundleToZip(bundle, screenshots.data ?? []);
      downloadBlob(blob, `${bundle.suggestedName}.zip`);
    } finally {
      setBusy(false);
    }
  };

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm" disabled={busy}>
          <DownloadIcon className="size-3.5" />
          {busy ? 'Packaging…' : 'Download'}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent className="min-w-[15rem]">
        <DropdownMenuLabel>Complete bundle</DropdownMenuLabel>
        <DropdownMenuItem onSelect={() => void downloadZip()}>
          <FileArchiveIcon className="size-4" />
          complete-report.zip
        </DropdownMenuItem>
        <DropdownMenuItem
          onSelect={() =>
            downloadJson(renderAnalysisJson(result), `${bundle.suggestedName}-analysis.json`)
          }
        >
          <FileJson2Icon className="size-4" />
          analysis.json
        </DropdownMenuItem>

        <DropdownMenuSeparator />
        <DropdownMenuLabel>Individual reports</DropdownMenuLabel>
        {REPORT_DEFINITIONS.map((definition) => {
          const file = bundle.files.find((candidate) => candidate.path === definition.file);
          if (!file) return null;
          return (
            <DropdownMenuItem key={definition.file} onSelect={() => downloadText(file)}>
              <FileTextIcon className="size-4" />
              {definition.file}
            </DropdownMenuItem>
          );
        })}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
