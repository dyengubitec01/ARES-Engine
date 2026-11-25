// created by ARES team [2026-04-28]
import { useState } from 'react';
import { submitSurvey, SurveyData } from '../../../services/board.service';
import { STEPS } from './surveySteps';

export function useSurveyForm() {
  const [currentStep, setCurrentStep] = useState(0);
  const [answers, setAnswers] = useState<Record<string, number | string>>({});
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [isDone, setIsDone] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  const handleRestart = () => {
    setAnswers({});
    setCurrentStep(0);
    setIsDone(false);
  };

  const step = STEPS[currentStep];
  const totalSteps = STEPS.length;

  const isStepComplete = (): boolean => {
    if (!step) return false;
    if (step.type === 'rating') {
      return step.questions.every((q) => answers[q.key] !== undefined);
    }
    return step.questions
      .filter((q) => q.required)
      .every((q) => {
        const val = answers[q.key];
        return typeof val === 'string' && val.trim().length > 0;
      });
  };

  const handleRatingChange = (key: string, value: number) => {
    setAnswers((prev) => ({ ...prev, [key]: value }));
  };

  const handleTextChange = (key: string, value: string) => {
    setAnswers((prev) => ({ ...prev, [key]: value }));
  };

  const handleNext = () => {
    if (currentStep < totalSteps - 1) {
      setCurrentStep((prev) => prev + 1);
      setSubmitError(null);
    }
  };

  const handlePrev = () => {
    if (currentStep > 0) {
      setCurrentStep((prev) => prev - 1);
      setSubmitError(null);
    }
  };

  const handleSubmit = async () => {
    setSubmitError(null);
    setIsSubmitting(true);
    try {
      const data: SurveyData = {
        loginUnderstand: answers.loginUnderstand as number,
        loginSimple: answers.loginSimple as number,
        homeIntuitive: answers.homeIntuitive as number,
        homeInputPosition: answers.homeInputPosition as number,
        homeNaturalStart: answers.homeNaturalStart as number,
        chatSpeed: answers.chatSpeed as number,
        chatEasy: answers.chatEasy as number,
        chatLength: answers.chatLength as number,
        chatProcessHelpful: answers.chatProcessHelpful as number,
        sourceVisible: answers.sourceVisible as number,
        sourceUiEasy: answers.sourceUiEasy as number,
        sourceTrust: answers.sourceTrust as number,
        docUploadEasy: answers.docUploadEasy as number,
        docStatusClear: answers.docStatusClear as number,
        docAiKnowledge: answers.docAiKnowledge as number,
        workHelpful: answers.workHelpful as number,
        workBetterThanLlm: answers.workBetterThanLlm as number,
        bestFeature: (answers.bestFeature as string) || '',
        worstFeature: (answers.worstFeature as string) || '',
        freeComment: (answers.freeComment as string) || '',
      };
      await submitSurvey(data);
      setIsDone(true);
    } catch {
      setSubmitError('설문 제출에 실패했습니다. 잠시후 다시 시도해주세요.');
    } finally {
      setIsSubmitting(false);
    }
  };

  const isLastStep = currentStep === totalSteps - 1;
  const progressPercent = ((currentStep + 1) / totalSteps) * 100;

  return {
    currentStep,
    answers,
    isSubmitting,
    isDone,
    submitError,
    step,
    totalSteps,
    isLastStep,
    progressPercent,
    isStepComplete,
    handleRatingChange,
    handleTextChange,
    handleNext,
    handlePrev,
    handleRestart,
    handleSubmit,
  };
}