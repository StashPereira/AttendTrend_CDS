import React from 'react';
import {render, screen, fireEvent} from '@testing-library/react';
import {it, expect, vi} from 'vitest';
import {AppContext, RecordModal} from '../src/App';
import {ImportReview} from '../src/pages';

const context:any = {semester:{id:1,name:'Odd semester',start_date:'2026-06-15',end_date:'2026-10-03'},subjects:[{id:1,code:'P101',name:'Physics practical',kind:'practical'}],busy:false,action:vi.fn()};
const show=(node:React.ReactNode)=>render(<AppContext.Provider value={context}>{node}</AppContext.Provider>);

it('filters annual calendar to selected semester and clips a vacation range',()=>{
 show(<ImportReview close={()=>{}} document={{kind:'calendar',status:'review',preview:{rows:[
 {title:'Odd holiday',start_date:'2026-07-01',end_date:'2026-07-01',kind:'holiday'},
 {title:'Even holiday',start_date:'2027-01-26',end_date:'2027-01-26',kind:'holiday'},
 {title:'Crossing break',start_date:'2026-10-01',end_date:'2026-10-10',kind:'holiday'}
 ]}}}/>);
 expect(screen.getByDisplayValue('Odd holiday')).toBeVisible();
 expect(screen.queryByDisplayValue('Even holiday')).toBeNull();
 expect(screen.getByLabelText('end_date row 2')).toHaveValue('2026-10-03');
 expect(screen.getByText(/Showing 2 of 3/)).toBeVisible();
});

it('choosing an existing timetable subject updates both code and name',()=>{
 show(<ImportReview close={()=>{}} document={{kind:'timetable',status:'review',preview:{rows:[{code:'',name:'OCR name',weekday:1,start_time:'09:00',end_time:'10:00',room:''}]}}}/>);
 fireEvent.change(screen.getByLabelText('Subject row 1'),{target:{value:'P101'}});
 expect(screen.getByLabelText('Subject row 1')).toHaveValue('P101');
 expect(screen.getByLabelText('name row 1')).toHaveValue('Physics practical');
});

it('asks for the complete subject semester lecture total',()=>{
 show(<RecordModal kind='subject' item={{name:'Physics',code:'P101',planned_lectures:40}} close={()=>{}}/>);
 expect(screen.getByLabelText(/How many lectures/)).toHaveValue(40);
 expect(screen.getByText(/including lectures already conducted/)).toBeVisible();
});
