import * as fs from 'fs';
import * as path from 'path';

/**
 * 4시간 단위 로테이션 로그 파일 writer.
 * 파일명: 2026-04-22-00.log (00-04시), 2026-04-22-04.log (04-08시), ...
 * 구조: {logDir}/{year}/{month}/{day}/{YYYY-MM-DD-HH}.log
 * 영구 보관 (자동 삭제 없음).
 */
export class LogFileRotator {
  private stream: fs.WriteStream | null = null;
  private currentSlot = '';

  constructor(private readonly logDir: string) {
    fs.mkdirSync(this.logDir, { recursive: true });
  }

  write(line: string): void {
    const slot = this.getCurrentSlot();

    if (slot !== this.currentSlot) {
      this.rotate(slot);
    }

    this.stream?.write(line.endsWith('\n') ? line : line + '\n');
  }

  close(): void {
    this.stream?.end();
    this.stream = null;
  }

  private rotate(slot: string): void {
    this.stream?.end();
    this.currentSlot = slot;

    // slot 형식: 2026-04-22-00
    const [year, month, day] = slot.split('-');
    const dayDir = path.join(this.logDir, year, month, day);
    fs.mkdirSync(dayDir, { recursive: true });

    const filePath = path.join(dayDir, `${slot}.log`);

    this.stream = fs.createWriteStream(filePath, { flags: 'a' });
    this.stream.on('error', (err) => {
      process.stderr.write(`[LogFileRotator] Write error: ${err.message}\n`);
    });
  }

  /**
   * 현재 시각의 4시간 슬롯 식별자 반환
   * 슬롯: 00(00-04), 04(04-08), 08(08-12), 12(12-16), 16(16-20), 20(20-24)
   * 예: 2026-04-22 13:45 → "2026-04-22-12"
   */
  private getCurrentSlot(): string {
    const d = new Date();
    const y = d.getFullYear();
    const M = String(d.getMonth() + 1).padStart(2, '0');
    const day = String(d.getDate()).padStart(2, '0');
    const hourSlot = String(Math.floor(d.getHours() / 4) * 4).padStart(2, '0');
    return `${y}-${M}-${day}-${hourSlot}`;
  }
}
