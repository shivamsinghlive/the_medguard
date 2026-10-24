"""
Fairness Specialist Agent - Suggestions based on dataset representation.
Performance and patient harm are not measured by this workflow.
"""

import ollama
from pydantic import BaseModel, ConfigDict, Field
from typing import Dict, List, Literal, Optional
import json
import re
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ============================================================================
# OUTPUT SCHEMAS - Keep unmeasured outcomes explicitly unavailable
# ============================================================================

class RecruitmentPlan(BaseModel):
    """Schema for specific recruitment strategy"""
    
    target_facilities: List[str] = Field(
        min_length=2,
        max_length=5,
        description="Specific hospitals/clinics in the user's geographic area"
    )
    
    timeline_months: int = Field(
        ge=1,
        le=24,
        description="Realistic timeline in months"
    )
    
    estimated_cost_usd: Optional[int] = Field(
        default=None,
        ge=0,
        description="Estimated recruitment cost if applicable"
    )
    
    specific_contacts: Optional[str] = Field(
        default=None,
        max_length=200,
        description="Specific organizations or contact info if known"
    )


class TechnicalMitigation(BaseModel):
    """Schema for immediate technical fixes"""
    
    method: Literal["SMOTE", "class_weighting", "undersampling", "separate_models"]
    
    python_code: str = Field(
        max_length=500,
        description="Working Python code to implement"
    )
    
    expected_improvement: Literal[
        "Not measured. Evaluate on held-out data before claiming improvement."
    ] = "Not measured. Evaluate on held-out data before claiming improvement."

    limitations: str = Field(
        max_length=200,
        description="What this method cannot solve"
    )


class HarmQuantification(BaseModel):
    """This workflow accepts no predictions or clinical-impact evidence.

    Null means unavailable, never zero harm. Reject supplied numbers instead of
    rounding or clamping invented values into a plausible-looking measurement.
    """
    model_config = ConfigDict(extra='forbid')
    status: Literal["not_measured"] = "not_measured"
    performance_gap_percentage: None = None
    patients_affected_per_100: None = None
    annual_impact_estimate: None = None
    clinical_consequence: Literal[
        "Not assessed. Dataset representation alone does not establish clinical harm."
    ] = "Not assessed. Dataset representation alone does not establish clinical harm."


class FairnessRecommendationSchema(BaseModel):
    """
    Complete fairness analysis with exact numbers
    Forces specificity - cannot be vague
    """
    bias_type: str = Field(description="Type of bias detected")
    
    severity: Literal["critical", "high", "medium", "low"]
    
    current_distribution: Dict[str, float] = Field(
        description="Actual percentages in dataset"
    )
    
    target_distribution: Dict[str, float] = Field(
        description="Target percentages for fairness"
    )
    
    exact_samples_needed: Dict[str, int] = Field(
        description="Exact number of additional samples per group"
    )
    
    predicted_harm: HarmQuantification = Field(default_factory=HarmQuantification)
    
    recruitment_plan: RecruitmentPlan
    
    immediate_technical_fix: TechnicalMitigation
    
    fits_user_timeline: bool = Field(
        description="Can recruitment be done in user's timeline?"
    )
    
    recommendation_priority: str = Field(
        max_length=300,
        description="Which approach to take given user constraints"
    )


# ============================================================================
# FAIRNESS SPECIALIST AGENT
# ============================================================================

class FairnessSpecialist:
    """
    Agent that provides exact, quantified fairness recommendations
    """
    
    def __init__(self):
        print("✅ Fairness Specialist Agent initialized")
    
    def analyze_bias(
        self,
        bias_info: Dict,
        user_context: Dict,
        statistics: Dict
    ) -> FairnessRecommendationSchema:
        """
        Generate exact, context-aware fairness recommendations
        
        Args:
            bias_info: Detected bias (from statistical analysis)
            user_context: User's project constraints
            statistics: Exact numbers from Python
        """
        
        # Build prompt with ALL context
        prompt = f"""
You are a dataset representation reviewer. Suggest actions grounded in the provided statistics.
This workflow has no held-out predictions, model evaluation, or clinical-impact evidence.
Do not infer performance gaps, misdiagnoses, affected-patient counts, annual harm,
or accuracy improvements from representation. Do not include such claims in ANY
free-text field. Unknown is not zero. Return the fixed unavailable fields below.

DETECTED BIAS:
- Type: {bias_info.get('type', 'demographic_imbalance')}
- Current distribution: {bias_info.get('distribution', {})}
- Underrepresented group: {bias_info.get('minority_group', 'N/A')}

EXACT STATISTICS (from Python - these are CORRECT):
- Total samples: {statistics.get('total_samples', 0)}
- Samples needed for balance: {statistics.get('samples_needed', 0)}
- Current imbalance: {statistics.get('imbalance_pct', 0)}%

USER CONSTRAINTS:
- Timeline: {user_context.get('timeline_days', 'unknown')} days
- Location: {user_context.get('location', 'unknown')}
- Can collect data: {user_context.get('can_collect_data', 'unknown')}
- Use case: {user_context.get('use_case', 'unknown')}
- Model type: {user_context.get('model_type', 'unknown')}

Provide response as valid JSON matching this EXACT structure:
{{
  "bias_type": "gender_imbalance" or similar,
  "severity": "critical" or "high" or "medium" or "low",
  "current_distribution": {{"Male": 73.0, "Female": 27.0}},
  "target_distribution": {{"Male": 50.0, "Female": 50.0}},
  "exact_samples_needed": {{"Female": 552}},
  
  "predicted_harm": {{
    "status": "not_measured",
    "performance_gap_percentage": null,
    "patients_affected_per_100": null,
    "clinical_consequence": "Not assessed. Dataset representation alone does not establish clinical harm.",
    "annual_impact_estimate": null
  }},
  
  "recruitment_plan": {{
    "target_facilities": ["Specific Hospital 1 in {user_context.get('location', 'area')}", "Specific Clinic 2"],
    "timeline_months": 6,
    "estimated_cost_usd": 45000,
    "specific_contacts": "Organization names if known"
  }},
  
  "immediate_technical_fix": {{
    "method": "SMOTE",
    "python_code": "from imblearn.over_sampling import SMOTE\\nsmote = SMOTE()\\nX_res, y_res = smote.fit_resample(X, y)",
    "expected_improvement": "Not measured. Evaluate on held-out data before claiming improvement.",
    "limitations": "Synthetic data may not capture all real-world variation. SMOTE creates synthetic samples based on existing patterns, which may not fully represent true demographic diversity."
  }},
  
  "fits_user_timeline": false,
  "recommendation_priority": "Given 60-day timeline, use SMOTE immediately..."
}}

CRITICAL RULES:
- Use EXACT numbers from statistics provided (don't make up new numbers)
- Provide SPECIFIC facility names in user's location
- Timeline must be realistic (recruitment takes 4-6 months minimum)
- Cost estimates should be reasonable ($20K-$100K range)
- Give SPECIFIC python code that works
- Explain why recommendation fits user's constraints
- Leave harm and performance estimates null. Preserve the fixed not-measured messages.

CRITICAL JSON FORMAT REQUIREMENTS:
- Use double quotes for all strings (not single quotes)
- No trailing commas before closing braces }} or brackets ]
- All keys must be in double quotes
- Ensure proper comma placement between JSON elements
- No comments or extra text outside the JSON object

Respond with ONLY valid JSON, no other text. Start with {{ and end with }}.
"""
        
        try:
            response = ollama.generate(
                model='llama3.2:3b',
                prompt=prompt,
                options={
                    'temperature': 0.2,  # Low for consistency
                    'num_predict': 1000   # Allow longer response
                }
            )
            
            response_text = response['response'].strip()
            
            # Clean JSON - multiple strategies
            if '```json' in response_text:
                response_text = response_text.split('```json')[1].split('```')[0].strip()
            elif '```' in response_text:
                response_text = response_text.split('```')[1].split('```')[0].strip()
            
            # Try to extract JSON object if there's extra text
            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                response_text = json_match.group(0)
            
            # Try to fix common JSON issues
            original_text = response_text  # Keep original for error reporting
            # Remove trailing commas before closing braces/brackets
            response_text = re.sub(r',(\s*[}\]])', r'\1', response_text)
            # Fix single quotes to double quotes (basic - only for simple cases)
            response_text = re.sub(r"'([^']*)':", r'"\1":', response_text)
            response_text = re.sub(r":\s*'([^']*)'", r': "\1"', response_text)
            
            # Parse and validate
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError as json_err:
                # If repair failed, try original text
                try:
                    result = json.loads(original_text)
                except:
                    # Log the problematic JSON for debugging
                    print(f"   JSON parse error at position {json_err.pos}: {json_err.msg}")
                    print(f"   Problematic JSON snippet: {response_text[max(0, json_err.pos-50):json_err.pos+50]}")
                    raise json_err
            
            # Schema rejection sends unsupported measurements to the unavailable fallback.
            validated = FairnessRecommendationSchema(**result)
            
            print("✅ Structured fairness recommendation generated")
            return validated
            
        except Exception as e:
            print(f"⚠️  AI generation failed: {e}")
            print("   Using fallback recommendation...")
            
            # Fallback to safe default
            return self._create_fallback_recommendation(bias_info, statistics, user_context)
    
    def _create_fallback_recommendation(
        self,
        bias_info: Dict,
        statistics: Dict,
        user_context: Dict
    ) -> FairnessRecommendationSchema:
        """
        Safe fallback if AI fails
        """
        minority_group = bias_info.get('minority_group', 'underrepresented')
        samples_needed = statistics.get('samples_needed', 0)
        
        return FairnessRecommendationSchema(
            bias_type=bias_info.get('type', 'demographic_imbalance'),
            severity="high",
            current_distribution=bias_info.get('distribution', {}),
            target_distribution={"balanced": 50.0},
            exact_samples_needed={minority_group: samples_needed},
            
            predicted_harm=HarmQuantification(),

            recruitment_plan=RecruitmentPlan(
                target_facilities=[
                    f"Community health centers serving {minority_group} populations",
                    "Academic medical centers with diverse patient base"
                ],
                timeline_months=6,
                estimated_cost_usd=None
            ),
            
            immediate_technical_fix=TechnicalMitigation(
                method="SMOTE",
                python_code="from imblearn.over_sampling import SMOTE\nsmote = SMOTE(random_state=42)\nX_balanced, y_balanced = smote.fit_resample(X, y)",
                expected_improvement="Not measured. Evaluate on held-out data before claiming improvement.",
                limitations="Synthetic data may not capture all real-world variation"
            ),
            
            fits_user_timeline=False,
            recommendation_priority="Use technical mitigation immediately while planning data collection"
        )


# Test
if __name__ == "__main__":
    print("=" * 60)
    print("Testing Fairness Specialist Agent")
    print("=" * 60)
    
    specialist = FairnessSpecialist()
    
    # Simulate bias detection results
    bias_info = {
        'type': 'gender_imbalance',
        'distribution': {'Male': 73.0, 'Female': 27.0},
        'minority_group': 'Female'
    }
    
    # Exact statistics from Python
    statistics = {
        'total_samples': 1200,
        'male_count': 876,
        'female_count': 324,
        'samples_needed': 552,  # 876 - 324
        'imbalance_pct': 23.0   # |73 - 50|
    }
    
    # User context
    user_context = {
        'timeline_days': 60,
        'location': 'Boston',
        'can_collect_data': 'maybe',
        'use_case': 'clinical_deployment',
        'model_type': 'Random Forest'
    }
    
    print("\n📊 Input:")
    print(f"Bias: {bias_info['type']}")
    print(f"Distribution: {bias_info['distribution']}")
    print(f"Samples needed: {statistics['samples_needed']}")
    print(f"User timeline: {user_context['timeline_days']} days")
    
    # Generate recommendation
    print("\n🤖 Generating AI recommendation with schema enforcement...")
    recommendation = specialist.analyze_bias(bias_info, user_context, statistics)
    
    # Display structured output
    print("\n" + "=" * 60)
    print("📋 STRUCTURED FAIRNESS RECOMMENDATION")
    print("=" * 60)
    
    print(f"\n🎯 Bias Type: {recommendation.bias_type}")
    print(f"⚠️  Severity: {recommendation.severity}")
    
    print(f"\n📊 Distribution:")
    print(f"Current: {recommendation.current_distribution}")
    print(f"Target:  {recommendation.target_distribution}")
    
    print(f"\n🔢 Exact Samples Needed:")
    for group, count in recommendation.exact_samples_needed.items():
        print(f"  • {group}: {count} additional patients")
    
    print("\nPerformance and clinical impact: not measured")
    print(f"  • Clinical consequence: {recommendation.predicted_harm.clinical_consequence}")
    
    print(f"\n🏥 Recruitment Plan:")
    print(f"  • Facilities: {recommendation.recruitment_plan.target_facilities}")
    print(f"  • Timeline: {recommendation.recruitment_plan.timeline_months} months")
    if recommendation.recruitment_plan.estimated_cost_usd:
        print(f"  • Cost: ${recommendation.recruitment_plan.estimated_cost_usd:,}")
    
    print(f"\n⚡ Immediate Fix:")
    print(f"  • Method: {recommendation.immediate_technical_fix.method}")
    print(f"  • Expected: {recommendation.immediate_technical_fix.expected_improvement}")
    print(f"  • Code:\n{recommendation.immediate_technical_fix.python_code}")
    
    print(f"\n⏰ Fits User Timeline: {recommendation.fits_user_timeline}")
    print(f"\n💡 Priority: {recommendation.recommendation_priority}")
    
    print("\n✅ Fairness Specialist test complete!")
    print("   Output structure validated; free-text suggestions still require review.")
