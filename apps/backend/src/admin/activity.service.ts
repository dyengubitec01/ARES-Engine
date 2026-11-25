import { Injectable, Logger } from '@nestjs/common';
import { InjectDataSource } from '@nestjs/typeorm';
import { DataSource } from 'typeorm';
import { Cron } from '@nestjs/schedule';
import { BusinessException } from '../common/exceptions/business.exception';
import {
  ResponseCode,
  getHttpStatus,
} from '../common/constants/response-codes';

export interface ActivityRow {
  user_id: string;
  user_name: string;
  department: string | null;
  job_title: string | null;
  missed_days: number;
  three_day_count: number;
  five_day_count: number;
  question_count: number;
  upload_count: number;
  other_citation_count: number;
  self_citation_count: number;
  feedback_count: number;
  answer_suggestion_count: number;
  adoption_score: number;
  persona_score: number;
  heritage_score: number;
  expert_score: number;
  total_score: number;
  eligible: boolean;
  period_name: string;
  dept_multiplier: number;
  dept_eligible_ratio: number;
  last_activity_at: Date | null;
  last_activity_type: string | null;
  updated_at: Date;
}

@Injectable()
export class ActivityService {
  private readonly logger = new Logger(ActivityService.name);

  constructor(
    @InjectDataSource() private readonly dataSource: DataSource,
  ) {}

  /**
   * 30분마다 Materialized View 자동 갱신
   */
  @Cron('*/30 * * * *')
  async autoRefresh(): Promise<void> {
    try {
      await this.refresh();
      this.logger.log('user_activity_summary auto-refreshed (30min)');
    } catch (error) {
      const err = error as Error;
      this.logger.error(`Auto-refresh failed: ${err.message}`);
    }
  }

  /**
   * 매일 자정 일배치 (미접속 감점 / 연속 접속 가점 / 월 리셋 반영)
   * Materialized View 정의가 매일 다시 SELECT를 돌리므로 동일하게 REFRESH 사용
   */
  @Cron('0 0 * * *')
  async dailyBatch(): Promise<void> {
    try {
      await this.refresh();
      this.logger.log('user_activity_summary daily batch refreshed');
    } catch (error) {
      const err = error as Error;
      this.logger.error(`Daily batch failed: ${err.message}`);
    }
  }

  /**
   * Materialized View 수동 갱신 (CONCURRENTLY)
   */
  async refresh(): Promise<Date> {
    const schema = (this.dataSource.options as any).schema || 'rag';
    await this.dataSource.query(
      `REFRESH MATERIALIZED VIEW CONCURRENTLY "${schema}".user_activity_summary`,
    );
    return new Date();
  }

  /**
   * 전체 사용자 활동 랭킹 조회 (total_score desc)
   */
  async getActivityList(page: number, limit: number) {
    const offset = (page - 1) * limit;

    const schema = (this.dataSource.options as any).schema || 'rag';
    const [items, totalResult] = await Promise.all([
      this.dataSource.query<ActivityRow[]>(
        `SELECT * FROM "${schema}".user_activity_summary
         ORDER BY total_score DESC, last_activity_at DESC NULLS LAST
         LIMIT $1 OFFSET $2`,
        [limit, offset],
      ),
      this.dataSource.query<{ total: string }[]>(
        `SELECT COUNT(*)::int AS total FROM "${schema}".user_activity_summary`,
      ),
    ]);

    const total = Number(totalResult[0]?.total ?? 0);

    return {
      items: items.map((row, idx) => ({
        rank: offset + idx + 1,
        ...this.toListDto(row),
      })),
      meta: {
        total,
        page,
        limit,
        totalPages: Math.ceil(total / limit),
      },
    };
  }

  /**
   * 사용자 상세 (rank + 카테고리별 분리)
   */
  async getActivityByUserId(userId: string) {
    const rows = await this.dataSource.query<
      Array<ActivityRow & { rank: string }>
    >(
      `SELECT * FROM (
         SELECT *, RANK() OVER (ORDER BY total_score DESC) AS rank
         FROM "${(this.dataSource.options as any).schema || 'rag'}".user_activity_summary
       ) ranked
       WHERE user_id = $1`,
      [userId],
    );

    if (!rows.length) {
      throw new BusinessException(
        ResponseCode.ADMIN_ACTIVITY_NOT_FOUND,
        undefined,
        getHttpStatus(ResponseCode.ADMIN_ACTIVITY_NOT_FOUND),
      );
    }

    const row = rows[0];
    return {
      rank: Number(row.rank),
      ...this.toDetailDto(row),
    };
  }

  /**
   * 리스트용 DTO (랭킹 테이블에 보일 항목)
   */
  private toListDto(row: ActivityRow) {
    return {
      userId: row.user_id,
      name: row.user_name,
      department: row.department,
      jobTitle: row.job_title,
      totalScore: Number(row.total_score),
      eligible: row.eligible,
      questionCount: Number(row.question_count),
      uploadCount: Number(row.upload_count),
      otherCitationCount: Number(row.other_citation_count),
      lastActivityAt: row.last_activity_at,
      lastActivityType: row.last_activity_type,
    };
  }

  /**
   * 상세 DTO (Persona/Heritage/EXpert 분리 표시)
   */
  private toDetailDto(row: ActivityRow) {
    return {
      userId: row.user_id,
      name: row.user_name,
      department: row.department,
      jobTitle: row.job_title,
      totalScore: Number(row.total_score),
      eligible: row.eligible,
      period: row.period_name,
      deptMultiplier: Number(row.dept_multiplier),
      deptEligibleRatio: Number(row.dept_eligible_ratio),
      persona: {
        score: Number(row.persona_score),
        missedDays: Number(row.missed_days),
        threeDayStreakCount: Number(row.three_day_count),
        fiveDayStreakCount: Number(row.five_day_count),
        questionCount: Number(row.question_count),
      },
      heritage: {
        score: Number(row.heritage_score),
        uploadCount: Number(row.upload_count),
        otherCitationCount: Number(row.other_citation_count),
        selfCitationCount: Number(row.self_citation_count),
      },
      expert: {
        score: Number(row.expert_score),
        feedbackCount: Number(row.feedback_count),
        answerSuggestionCount: Number(row.answer_suggestion_count),
        adoptionScore: Number(row.adoption_score),
      },
      lastActivityAt: row.last_activity_at,
      lastActivityType: row.last_activity_type,
      updatedAt: row.updated_at,
    };
  }
}
