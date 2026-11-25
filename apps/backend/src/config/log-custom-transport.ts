import build from 'pino-abstract-transport';
import { LogFileRotator } from './log-file-rotator';

const LEVEL_MAP: Record<number, string> = {
  10: 'TRACE',
  20: 'DEBUG',
  30: 'INFO',
  40: 'WARN',
  50: 'ERROR',
  60: 'FATAL',
};

function formatDate(ts: number): string {
  const d = new Date(ts);
  const y = d.getFullYear();
  const M = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  const h = String(d.getHours()).padStart(2, '0');
  const m = String(d.getMinutes()).padStart(2, '0');
  const s = String(d.getSeconds()).padStart(2, '0');
  return `${y}-${M}-${day} ${h}:${m}:${s}`;
}

function formatLine(obj: Record<string, unknown>): string {
  const date = formatDate((obj.time as number) || Date.now());
  const level = LEVEL_MAP[(obj.level as number) ?? 30] || 'INFO';
  const context = (obj.context as string) || '-';
  const msg = (obj.msg as string) || '-';

  return (
    `[APP-LOG] [DATE] ${date} | ` +
    `[LEVEL] ${level} | ` +
    `[CONTEXT] ${context} | ` +
    `[MSG] ${msg}`
  );
}

export default async function (opts: { logDir?: string }) {
  let rotator: LogFileRotator | null = null;

  if (opts.logDir) {
    rotator = new LogFileRotator(opts.logDir);
  }

  return build(
    async function (source) {
      for await (const obj of source) {
        const line = formatLine(obj) + '\n';
        process.stdout.write(line);
        rotator?.write(line);
      }
    },
    { close: async () => rotator?.close() },
  );
}
