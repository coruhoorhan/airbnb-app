import Joi from 'joi';

export const authSchema = Joi.object({
  email: Joi.string().email().required().messages({
    'string.email': 'Geçerli bir email gerekli.',
    'any.required': 'Email alanı zorunludur.',
    'string.empty': 'Email alanı boş bırakılamaz.'
  })
});
